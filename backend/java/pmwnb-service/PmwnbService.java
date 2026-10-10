package weka.classifiers.bayes.PMWNB.service;

import com.sun.net.httpserver.HttpExchange;
import com.sun.net.httpserver.HttpServer;
import org.json.JSONArray;
import org.json.JSONObject;
import weka.classifiers.AbstractClassifier;
import weka.classifiers.Classifier;
import weka.classifiers.bayes.PMWNB.PMWNB.PMWNB;
import weka.core.Attribute;
import weka.core.DenseInstance;
import weka.core.Instance;
import weka.core.Instances;
import weka.core.SerializationHelper;
import weka.core.converters.ConverterUtils.DataSource;
import java.io.File;
import java.io.IOException;
import java.io.OutputStream;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.util.Collections;
import java.util.Iterator;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.Random;
import java.util.concurrent.Executors;

/** PMWNB HTTP service. */
public final class PmwnbService {
    /**
     * 模型缓存预算（字节）。
     *
     * 原来按条目数限制（capacity=4），但模型大小差三个数量级 —— 实测同目录下
     * 47.5 / 98.6 / 123.5 / 178.9 / 205.6 MB 各一份，反序列化后按 1.4 倍膨胀，
     * 4 个"条目"最坏情况是 1.15 GB，-Xmx512m 必然 OutOfMemoryError。
     * 上限必须按字节算。
     *
     * 默认取堆上限的 55%，可用 -Dpmwnb.modelCacheBudgetBytes 覆盖。
     */
    private static final long MODEL_CACHE_BUDGET_BYTES = Long.getLong(
            "pmwnb.modelCacheBudgetBytes",
            Math.max(48L << 20, (long) (Runtime.getRuntime().maxMemory() * 0.55)));

    /** 反序列化后的堆占用约为模型文件的 1.4 倍（实测 205 MB 文件 → 287 MB 堆）。 */
    private static final double MODEL_HEAP_FACTOR = 1.4;

    /** 缓存条目：分类器 + 估算堆占用。 */
    private static final class CachedModel {
        final Classifier classifier;
        final long bytes;

        CachedModel(Classifier classifier, long bytes) {
            this.classifier = classifier;
            this.bytes = bytes;
        }
    }

    /**
     * 模型缓存（LRU，按 MODEL_CACHE_BUDGET_BYTES 限总量）。
     * 反序列化一个模型要读几百 MB 文件，所以缓存结果；但必须有上限，否则读过的模型
     * 会一直常驻堆内，内存随「历史上访问过多少个模型」无限增长。
     * 访问顺序由 LinkedHashMap(accessOrder=true) 维护，get/put 由 synchronizedMap 保证原子。
     */
    private static final Map<String, CachedModel> MODEL_CACHE =
            Collections.synchronizedMap(new LinkedHashMap<String, CachedModel>(8, 0.75f, true));

    /** 估算模型反序列化后的堆占用。 */
    private static long estimateModelBytes(String modelPath) {
        return (long) (new File(modelPath).length() * MODEL_HEAP_FACTOR);
    }

    /**
     * 按预算淘汰最久未使用的模型，直到能装下 {@code incomingBytes}。
     *
     * 单条超过预算时不淘汰自己（否则大模型永远缓存不上，每次预测都要重新反序列化），
     * 而是把缓存清空后单独放它 —— 实测 205 MB 模型占 287 MB 堆，-Xmx512m 装得下。
     */
    private static void evictFor(long incomingBytes) {
        synchronized (MODEL_CACHE) {
            long total = 0;
            for (CachedModel cached : MODEL_CACHE.values()) {
                total += cached.bytes;
            }
            // entrySet() 按访问顺序迭代，从头删就是淘汰最久未使用的
            Iterator<Map.Entry<String, CachedModel>> it = MODEL_CACHE.entrySet().iterator();
            while (it.hasNext() && total + incomingBytes > MODEL_CACHE_BUDGET_BYTES) {
                Map.Entry<String, CachedModel> eldest = it.next();
                total -= eldest.getValue().bytes;
                it.remove();
                System.out.println("[PmwnbService] 缓存预算不足，淘汰最久未使用的模型: " + eldest.getKey());
            }
        }
    }

    /**
     * 读模型；未命中先按预算腾出空间，再反序列化。
     *
     * **顺序不能反**：如果等 put 时再淘汰，新模型已经在堆里了，新旧两份同时存活，
     * 照样 OOM —— 淘汰必须发生在反序列化之前。
     */
    private static Classifier loadModel(String modelPath) throws Exception {
        CachedModel cached = MODEL_CACHE.get(modelPath);
        if (cached != null) {
            return cached.classifier;
        }
        long estimated = estimateModelBytes(modelPath);
        evictFor(estimated);
        Classifier classifier;
        try {
            classifier = (Classifier) SerializationHelper.read(modelPath);
        } catch (Exception e) {
            throw new RuntimeException("模型加载失败: " + e.getMessage(), e);
        }
        MODEL_CACHE.put(modelPath, new CachedModel(classifier, estimated));
        return classifier;
    }

    /** 训练完成后把新模型放进缓存（同样先按预算腾空间）。 */
    private static void cacheModel(String modelPath, Classifier classifier) {
        long estimated = estimateModelBytes(modelPath);
        evictFor(estimated);
        MODEL_CACHE.put(modelPath, new CachedModel(classifier, estimated));
    }

    private PmwnbService() {}

    public static void main(String[] args) throws Exception {
        int port = args.length > 0 ? Integer.parseInt(args[0]) : 12313;
        HttpServer server = HttpServer.create(new InetSocketAddress("127.0.0.1", port), 0);
        server.createContext("/health", PmwnbService::handleHealth);
        server.createContext("/train", PmwnbService::handleTrain);
        server.createContext("/predict", PmwnbService::handlePredict);
        server.createContext("/shutdown", PmwnbService::handleShutdown);
        server.setExecutor(Executors.newFixedThreadPool(4));
        server.start();
        System.out.println("[PmwnbService] PMWNB listening on 127.0.0.1:" + port);
    }

    private static void handleHealth(HttpExchange ex) throws IOException {
        respond(ex, 200, new JSONObject().put("status", "ok")
                .put("algorithm", "PMWNB").put("model_cache", MODEL_CACHE.size()));
    }

    private static void handleTrain(HttpExchange ex) throws IOException {
        try {
            JSONObject req = new JSONObject(readBody(ex));
            String datasetPath = req.getString("dataset_path");
            String modelSavePath = req.getString("model_save_path");
            JSONObject parameters = req.optJSONObject("training_parameters");
            if (parameters == null) parameters = new JSONObject();

            Instances data = loadDataset(datasetPath);
            JSONArray riskLabels = req.optJSONArray("risk_labels");

            long started = System.nanoTime();

            // 顺序很关键：**先交叉验证，再训练全量模型**（理由同
            // NbAlgorithmService.handleTrain）。全量模型和 CV 的折模型都是百 MB 级对象
            // （本数据集 279 属性，序列化后 215 MB，堆内约 300 MB），-Xmx512m 装不下
            // 两个同时存活的对象。CV 放前面，折模型用完即弃。
            //
            // CV 的模板必须是**未训练**的：makeCopy 的实现是「把整个分类器序列化成
            // 一个 byte[] 再反序列化」，传已训练模型进去等于凭空再复制两份。
            // 每折本来就要 buildClassifier(train) 重新训练，复制已训练模型没有任何收益。
            JSONObject quality = calculateQualityMetrics(new PMWNB(), data, riskLabels);

            // 评估指标使用固定随机种子的分层交叉验证；保存的模型用全量数据训练。
            PMWNB classifier = new PMWNB();
            classifier.buildClassifier(data);
            SerializationHelper.write(modelSavePath, classifier);
            cacheModel(modelSavePath, classifier);

            JSONArray distribution = new JSONArray();
            for (int i = 0; i < data.numClasses(); i++) {
                distribution.put(new JSONObject().put("class", data.classAttribute().value(i))
                        .put("count", countClass(data, i)));
            }
            JSONObject metrics = new JSONObject()
                    .put("algorithm", "PMWNB")
                    .put("accuracy", quality.get("accuracy"))
                    .put("precision", quality.get("precision"))
                    .put("recall", quality.get("recall"))
                    .put("f1", quality.get("f1"))
                    .put("specificity", quality.get("specificity"))
                    .put("g_mean", quality.get("g_mean"))
                    .put("risk_recall", quality.get("risk_recall"))
                    .put("risk_f1", quality.get("risk_f1"))
                    .put("cv_mean", quality.get("cv_mean"))
                    .put("cv_std", quality.get("cv_std"))
                    .put("quality_availability", quality.get("quality_availability"))
                    .put("train_time_s", round((System.nanoTime() - started) / 1_000_000_000.0))
                    .put("num_instances", data.numInstances())
                    .put("num_attributes", data.numAttributes() - 1)
                    .put("num_classes", data.numClasses())
                    .put("class_distribution", distribution)
                    .put("model_saved_to", modelSavePath)
                    .put("dataset", datasetPath)
                    .put("training_parameters", parameters);
            respond(ex, 200, new JSONObject().put("success", true).put("metrics", metrics));
        } catch (Throwable e) {
            // 必须是 Throwable 而不是 Exception：OutOfMemoryError 继承自 Error，
            // catch (Exception) 接不住它。逃逸的后果是工作线程直接死掉、响应永远不发，
            // 客户端只能等到自己的超时（后端 TRAIN_TIMEOUT=600s），而模型文件其实
            // 已经写到盘上了 —— 表现为"训练卡住十分钟后失败，却留下一个孤儿模型"。
            respond(ex, 500, new JSONObject().put("success", false).put("error", message(e)));
        }
    }

    private static void handlePredict(HttpExchange ex) throws IOException {
        try {
            JSONObject req = new JSONObject(readBody(ex));
            String modelPath = req.getString("model_path");
            String arffPath = req.getString("arff_path");
            JSONObject features = req.optJSONObject("features");
            if (features == null) throw new IllegalArgumentException("缺少 features 字段");

            Classifier classifier = loadModel(modelPath);
            Instances header = new DataSource(arffPath).getStructure();
            if (header.classIndex() < 0) header.setClassIndex(header.numAttributes() - 1);
            Instance instance = buildInstance(header, features);
            double[] dist = classifier.distributionForInstance(instance);
            int argmax = 0;
            for (int i = 1; i < dist.length; i++) if (dist[i] > dist[argmax]) argmax = i;

            JSONArray classes = new JSONArray();
            for (int i = 0; i < dist.length; i++) {
                classes.put(new JSONObject().put("class", header.classAttribute().value(i))
                        .put("probability", round(dist[i])));
            }
            JSONObject data = new JSONObject().put("prediction_label", header.classAttribute().value(argmax))
                    .put("probability", round(dist[argmax])).put("class_distribution", classes);
            respond(ex, 200, new JSONObject().put("success", true).put("data", data));
        } catch (Throwable e) {
            // 同 handleTrain：OOM 是 Error，catch (Exception) 接不住，会让连接挂死。
            respond(ex, 500, new JSONObject().put("success", false).put("error", message(e)));
        }
    }

    private static Instances loadDataset(String path) throws Exception {
        Instances data = new DataSource(path).getDataSet();
        if (data == null || data.numAttributes() < 2) throw new IllegalArgumentException("数据集字段不足");
        if (data.classIndex() < 0) data.setClassIndex(data.numAttributes() - 1);
        data.deleteWithMissingClass();
        if (!data.classAttribute().isNominal()) throw new IllegalArgumentException("分类标签必须是名义型字段");
        return data;
    }

    private static Instance buildInstance(Instances header, JSONObject features) {
        DenseInstance instance = new DenseInstance(header.numAttributes());
        instance.setDataset(header);
        for (int i = 0; i < header.numAttributes(); i++) {
            if (i == header.classIndex()) { instance.setMissing(i); continue; }
            Attribute attr = header.attribute(i);
            String name = attr.name();
            if (!features.has(name)) { instance.setMissing(i); continue; }
            Object value = features.get(name);
            if (value == null || JSONObject.NULL.equals(value) || String.valueOf(value).trim().isEmpty()) {
                instance.setMissing(i); continue;
            }
            try {
                if (attr.isNumeric()) {
                    instance.setValue(i, value instanceof Number ? ((Number) value).doubleValue()
                            : Double.parseDouble(String.valueOf(value).trim()));
                } else if (attr.indexOfValue(String.valueOf(value)) >= 0) {
                    instance.setValue(i, String.valueOf(value));
                } else {
                    instance.setMissing(i);
                }
            } catch (Exception ignored) { instance.setMissing(i); }
        }
        return instance;
    }

    private static int countClass(Instances data, int classIndex) {
        int count = 0;
        for (int i = 0; i < data.numInstances(); i++) {
            if ((int) data.instance(i).classValue() == classIndex) count++;
        }
        return count;
    }

    /**
     * Calculate aggregate metrics and fold accuracy statistics without changing
     * the classifier used for the saved full-data model.
     *
     * @param untrainedTemplate 未训练的分类器模板。**不能传已训练模型**：
     *        AbstractClassifier.makeCopy 的实现是 new SerializedObject(classifier)，
     *        即"序列化成 byte[] 再反序列化"，传已训练模型等于凭空多复制两份。
     *        每折本来就要 buildClassifier(train) 重新训练，复制已训练模型没有任何收益。
     */
    private static JSONObject calculateQualityMetrics(
            Classifier untrainedTemplate, Instances data, JSONArray riskLabels) throws Exception {
        int folds = Math.min(10, data.numInstances());
        if (folds < 2) throw new IllegalArgumentException("交叉验证至少需要 2 条样本");

        Instances cvData = new Instances(data);
        Random random = new Random(1);
        cvData.randomize(random);
        if (cvData.classAttribute().isNominal()) cvData.stratify(folds);

        double[][] confusion = new double[data.numClasses()][data.numClasses()];
        double[] foldAccuracy = new double[folds];
        for (int fold = 0; fold < folds; fold++) {
            Classifier copy = AbstractClassifier.makeCopy(untrainedTemplate);
            Instances train = cvData.trainCV(folds, fold, random);
            Instances test = cvData.testCV(folds, fold);
            copy.buildClassifier(train);
            double correct = 0.0;
            double total = 0.0;
            for (int i = 0; i < test.numInstances(); i++) {
                Instance row = test.instance(i);
                if (row.classIsMissing()) continue;
                double[] distribution = copy.distributionForInstance(row);
                int predicted = 0;
                for (int c = 1; c < distribution.length; c++) {
                    if (distribution[c] > distribution[predicted]) predicted = c;
                }
                int actual = (int) row.classValue();
                double weight = row.weight();
                confusion[actual][predicted] += weight;
                total += weight;
                if (actual == predicted) correct += weight;
            }
            foldAccuracy[fold] = total == 0.0 ? Double.NaN : correct / total;
        }

        double diagonal = 0.0;
        for (int actual = 0; actual < confusion.length; actual++) {
            for (int predicted = 0; predicted < confusion[actual].length; predicted++) {
                if (actual == predicted) diagonal += confusion[actual][predicted];
            }
        }
        double weightedRecall = 0.0;
        double weightedPrecision = 0.0;
        double weightedF1 = 0.0;
        double weightedSpecificity = 0.0;
        for (int c = 0; c < confusion.length; c++) {
            double actualCount = 0.0;
            double predictedCount = 0.0;
            for (int i = 0; i < confusion.length; i++) {
                actualCount += confusion[c][i];
                predictedCount += confusion[i][c];
            }
            double tp = confusion[c][c];
            double fn = actualCount - tp;
            double fp = predictedCount - tp;
            double tn = totalWeight(confusion) - tp - fn - fp;
            double weight = totalWeight(confusion) == 0.0 ? 0.0 : actualCount / totalWeight(confusion);
            weightedRecall += weight * ratio(tp, tp + fn);
            weightedPrecision += weight * ratio(tp, tp + fp);
            weightedF1 += weight * f1(tp, fp, fn);
            weightedSpecificity += weight * ratio(tn, tn + fp);
        }

        boolean riskAvailable = false;
        double riskTp = 0.0;
        double riskActual = 0.0;
        double riskPredicted = 0.0;
        for (int actual = 0; actual < confusion.length; actual++) {
            boolean actualRisk = isRiskClass(data.classAttribute().value(actual), riskLabels);
            for (int predicted = 0; predicted < confusion[actual].length; predicted++) {
                boolean predictedRisk = isRiskClass(data.classAttribute().value(predicted), riskLabels);
                if (actualRisk) {
                    riskAvailable = true;
                    riskActual += confusion[actual][predicted];
                }
                if (predictedRisk) riskPredicted += confusion[actual][predicted];
                if (actualRisk && predictedRisk) riskTp += confusion[actual][predicted];
            }
        }

        double cvMean = mean(foldAccuracy);
        double cvStd = standardDeviation(foldAccuracy, cvMean);
        return new JSONObject()
                .put("accuracy", round(ratio(diagonal, totalWeight(confusion))))
                .put("precision", round(weightedPrecision))
                .put("recall", round(weightedRecall))
                .put("f1", round(weightedF1))
                .put("specificity", round(weightedSpecificity))
                .put("g_mean", round(Math.sqrt(Math.max(0.0, weightedRecall * weightedSpecificity))))
                .put("risk_recall", riskAvailable ? round(ratio(riskTp, riskActual)) : JSONObject.NULL)
                .put("risk_f1", riskAvailable
                        ? round(f1(riskTp, riskPredicted - riskTp, riskActual - riskTp))
                        : JSONObject.NULL)
                .put("cv_mean", Double.isNaN(cvMean) ? JSONObject.NULL : round(cvMean))
                .put("cv_std", Double.isNaN(cvStd) ? JSONObject.NULL : round(cvStd))
                .put("quality_availability", new JSONObject()
                        .put("risk_recall", availability(riskAvailable, "训练请求未提供有效风险类别映射"))
                        .put("risk_f1", availability(riskAvailable, "训练请求未提供有效风险类别映射"))
                        .put("cv_mean", availability(!Double.isNaN(cvMean), "交叉验证均值不可用"))
                        .put("cv_std", availability(!Double.isNaN(cvStd), "交叉验证标准差不可用")));
    }

    private static boolean isRiskClass(String label, JSONArray riskLabels) {
        if (riskLabels == null) return false;
        for (int i = 0; i < riskLabels.length(); i++) {
            if (label.equals(String.valueOf(riskLabels.opt(i)))) return true;
        }
        return false;
    }

    private static double totalWeight(double[][] confusion) {
        double total = 0.0;
        for (double[] row : confusion) {
            for (double value : row) total += value;
        }
        return total;
    }

    private static double ratio(double numerator, double denominator) {
        return denominator == 0.0 ? 0.0 : numerator / denominator;
    }

    private static double f1(double tp, double fp, double fn) {
        double precision = ratio(tp, tp + fp);
        double recall = ratio(tp, tp + fn);
        return ratio(2.0 * precision * recall, precision + recall);
    }

    private static double mean(double[] values) {
        double sum = 0.0;
        int count = 0;
        for (double value : values) {
            if (!Double.isNaN(value)) {
                sum += value;
                count++;
            }
        }
        return count == 0 ? Double.NaN : sum / count;
    }

    private static double standardDeviation(double[] values, double mean) {
        if (Double.isNaN(mean)) return Double.NaN;
        double sum = 0.0;
        int count = 0;
        for (double value : values) {
            if (!Double.isNaN(value)) {
                double delta = value - mean;
                sum += delta * delta;
                count++;
            }
        }
        return count == 0 ? Double.NaN : Math.sqrt(sum / count);
    }

    private static JSONObject availability(boolean available, String reason) {
        return new JSONObject().put("available", available).put("reason", available ? JSONObject.NULL : reason);
    }

    private static double round(double value) { return Math.round(value * 10000.0) / 10000.0; }
    private static String message(Throwable e) { return e.getMessage() == null ? e.toString() : e.getMessage(); }
    private static String readBody(HttpExchange ex) throws IOException {
        return new String(ex.getRequestBody().readAllBytes(), StandardCharsets.UTF_8);
    }
    private static void respond(HttpExchange ex, int code, JSONObject body) throws IOException {
        byte[] bytes = body.toString().getBytes(StandardCharsets.UTF_8);
        ex.getResponseHeaders().set("Content-Type", "application/json; charset=utf-8");
        ex.sendResponseHeaders(code, bytes.length);
        try (OutputStream output = ex.getResponseBody()) { output.write(bytes); }
    }

    private static void handleShutdown(HttpExchange ex) throws IOException {
        respond(ex, 200, new JSONObject().put("status", "stopping"));
        new Thread(() -> System.exit(0), "pmwnb-shutdown").start();
    }
}
