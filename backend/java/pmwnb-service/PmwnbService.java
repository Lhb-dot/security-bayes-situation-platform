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
import java.io.IOException;
import java.io.OutputStream;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.util.Random;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.Executors;

/** PMWNB HTTP service. */
public final class PmwnbService {
    private static final ConcurrentHashMap<String, Classifier> MODEL_CACHE = new ConcurrentHashMap<>();

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

            long started = System.nanoTime();
            PMWNB classifier = new PMWNB();
            classifier.buildClassifier(data);
            SerializationHelper.write(modelSavePath, classifier);
            MODEL_CACHE.put(modelSavePath, classifier);

            // 评估指标使用固定随机种子的分层交叉验证；保存的模型仍用上面的全量数据训练。
            JSONArray riskLabels = req.optJSONArray("risk_labels");
            JSONObject quality = calculateQualityMetrics(classifier, data, riskLabels);

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
        } catch (Exception e) {
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

            Classifier classifier = MODEL_CACHE.get(modelPath);
            if (classifier == null) {
                classifier = (Classifier) SerializationHelper.read(modelPath);
                MODEL_CACHE.put(modelPath, classifier);
            }
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
        } catch (Exception e) {
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
     */
    private static JSONObject calculateQualityMetrics(
            Classifier template, Instances data, JSONArray riskLabels) throws Exception {
        int folds = Math.min(10, data.numInstances());
        if (folds < 2) throw new IllegalArgumentException("交叉验证至少需要 2 条样本");

        Instances cvData = new Instances(data);
        Random random = new Random(1);
        cvData.randomize(random);
        if (cvData.classAttribute().isNominal()) cvData.stratify(folds);

        double[][] confusion = new double[data.numClasses()][data.numClasses()];
        double[] foldAccuracy = new double[folds];
        for (int fold = 0; fold < folds; fold++) {
            Classifier copy = AbstractClassifier.makeCopy(template);
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
    private static String message(Exception e) { return e.getMessage() == null ? e.toString() : e.getMessage(); }
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
