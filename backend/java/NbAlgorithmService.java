package com.security.bayes.nbservice;

import com.sun.net.httpserver.HttpExchange;
import com.sun.net.httpserver.HttpServer;
import org.json.JSONArray;
import org.json.JSONObject;
import weka.classifiers.Classifier;
import weka.classifiers.Evaluation;
import weka.classifiers.meta.FilteredClassifier;
import weka.classifiers.zh.A2WNB.A2WNB;
import weka.classifiers.zh.A2WNB.RODE;
import weka.classifiers.zh.CAVWNB.CAVWNB;
import weka.classifiers.zh.CAVWNB.WANBDistribution;
import weka.classifiers.zh.MVCAVWNB.EMAWNB;
import weka.classifiers.zh.MVCAVWNB.MVCAVWNB;
import weka.classifiers.mkx.DIWNB.DIWNB_HE;
import weka.core.Attribute;
import weka.core.DenseInstance;
import weka.core.Instance;
import weka.core.Instances;
import weka.core.SerializationHelper;
import weka.core.converters.ConverterUtils.DataSource;
import weka.filters.Filter;
import weka.filters.unsupervised.attribute.Remove;
import weka.filters.unsupervised.attribute.Discretize;

import java.io.IOException;
import java.io.OutputStream;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.util.Random;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.Executors;

/**
 * 真实 NB 算法 HTTP 服务。
 *
 * 每个算法 JAR 都复用本服务，启动参数为：<port> <algorithm-code>。
 * /train 对数据执行交叉验证、全量训练并保存 Weka 模型；/predict 加载模型执行真实预测。
 */
public final class NbAlgorithmService {
    private static final ConcurrentHashMap<String, Classifier> MODEL_CACHE = new ConcurrentHashMap<>();
    private static String algorithmCode;

    private NbAlgorithmService() {}

    public static void main(String[] args) throws Exception {
        int port = args.length > 0 ? Integer.parseInt(args[0]) : 12315;
        algorithmCode = args.length > 1 ? args[1].toUpperCase() : "A2WNB";
        Class.forName(classNameFor(algorithmCode));

        HttpServer server = HttpServer.create(new InetSocketAddress("127.0.0.1", port), 0);
        server.createContext("/health", NbAlgorithmService::handleHealth);
        server.createContext("/train", NbAlgorithmService::handleTrain);
        server.createContext("/predict", NbAlgorithmService::handlePredict);
        server.createContext("/shutdown", NbAlgorithmService::handleShutdown);
        server.setExecutor(Executors.newFixedThreadPool(4));
        server.start();
        System.out.println("[NbAlgorithmService] " + algorithmCode + " listening on 127.0.0.1:" + port);
    }

    private static String classNameFor(String code) {
        switch (code) {
            case "A2WNB": return "weka.classifiers.zh.A2WNB.A2WNB";
            case "CAVWNB": return "weka.classifiers.zh.CAVWNB.CAVWNB";
            case "DIWNB": return "weka.classifiers.mkx.DIWNB.DIWNB_HE";
            case "MAWNB": return "weka.classifiers.zh.MVCAVWNB.MVCAVWNB";
            case "EMAWNB": return "weka.classifiers.zh.MVCAVWNB.EMAWNB";
            default: throw new IllegalArgumentException("不支持的算法: " + code);
        }
    }

    private static void handleHealth(HttpExchange ex) throws IOException {
        respond(ex, 200, new JSONObject().put("status", "ok").put("algorithm", algorithmCode)
                .put("model_cache", MODEL_CACHE.size()));
    }

    private static void handleTrain(HttpExchange ex) throws IOException {
        try {
            JSONObject req = new JSONObject(readBody(ex));
            String datasetPath = req.getString("dataset_path");
            String modelSavePath = req.optString("model_save_path", "");
            if (modelSavePath.isEmpty()) {
                throw new IllegalArgumentException("缺少 model_save_path");
            }

            long started = System.nanoTime();
            Instances data = loadDataset(datasetPath);
            JSONObject parameters = req.optJSONObject("training_parameters");
            Classifier classifier = createClassifier(parameters == null ? new JSONObject() : parameters);
            classifier.buildClassifier(data);
            SerializationHelper.write(modelSavePath, classifier);
            MODEL_CACHE.put(modelSavePath, classifier);

            // 评估指标改用分层 10 折交叉验证（避免训练集重代入偏乐观）；
            // 保存的模型仍用全量数据训练（上面的 classifier.buildClassifier(data)）。
            Evaluation evaluation = new Evaluation(data);
            evaluation.crossValidateModel(classifier, data, 10, new Random(1));

            double accuracy = evaluation.pctCorrect() / 100.0;
            double recall = evaluation.weightedRecall();
            double precision = evaluation.weightedPrecision();
            double f1 = evaluation.weightedFMeasure();
            double specificity = evaluation.weightedTrueNegativeRate();
            double gMean = Math.sqrt(Math.max(0.0, recall * specificity));

            JSONArray distribution = new JSONArray();
            for (int i = 0; i < data.numClasses(); i++) {
                distribution.put(new JSONObject().put("class", data.classAttribute().value(i))
                        .put("count", countClass(data, i)));
            }

            JSONObject metrics = new JSONObject()
                    .put("algorithm", algorithmCode)
                    .put("accuracy", round(accuracy))
                    .put("precision", round(precision))
                    .put("recall", round(recall))
                    .put("f1", round(f1))
                    .put("specificity", round(specificity))
                    .put("g_mean", round(gMean))
                    .put("train_time_s", round((System.nanoTime() - started) / 1_000_000_000.0))
                    .put("num_instances", data.numInstances())
                    .put("num_attributes", data.numAttributes() - 1)
                    .put("num_classes", data.numClasses())
                    .put("class_distribution", distribution)
                    .put("model_saved_to", modelSavePath)
                    .put("dataset", datasetPath);
            metrics.put("training_parameters", parameters == null ? new JSONObject() : parameters);
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
            // 追加多视图预测 / 视图权重 / 特征加权条件概率（未接入算法返回空数组）
            JSONObject explain = buildExplain(classifier, instance, header);
            data.put("views", explain.getJSONArray("views"));
            data.put("view_weights", explain.getJSONArray("view_weights"));
            data.put("feature_evidence", explain.getJSONArray("feature_evidence"));
            respond(ex, 200, new JSONObject().put("success", true).put("data", data));
        } catch (Exception e) {
            respond(ex, 500, new JSONObject().put("success", false).put("error", message(e)));
        }
    }

    /**
     * 组装可解释性信息：多视图预测、视图权重、特征加权条件概率。
     *
     * 说明：序列化后的模型是 FilteredClassifierWithDiscretize（外层离散化包裹内层
     * 研究算法），因此先解包拿到真实算法实例，并用训练好的离散化过滤器把原始实例
     * 转成离散实例，再调用各算法的 per-view 方法。任一环节异常都回退为空解释，
     * 不影响预测主流程。PMWNB / DIWNB 本次未接入，返回空 views / feature_evidence。
     */
    private static JSONObject buildExplain(Classifier classifier, Instance instance, Instances header) {
        JSONObject explain = new JSONObject();
        explain.put("views", new JSONArray());
        explain.put("view_weights", new JSONArray());
        explain.put("feature_evidence", new JSONArray());
        try {
            if (!(classifier instanceof FilteredClassifier)) {
                return explain;
            }
            FilteredClassifier fc = (FilteredClassifier) classifier;
            Classifier base = fc.getClassifier();
            if (base == null) {
                return explain;
            }

            // 复刻 FilteredClassifier.distributionForInstance 的离散化步骤，得到离散实例
            Instance disc = instance;
            if (fc.getFilter() != null) {
                fc.getFilter().input(instance);
                disc = fc.getFilter().output();
            }

            JSONArray views = new JSONArray();
            JSONArray viewWeights = new JSONArray();
            JSONArray featureEvidence = new JSONArray();
            String calculationMethod = null;

            if (base instanceof CAVWNB) {
                // 单视图（原始属性视图），无独立视图；但提供特征加权条件概率
                CAVWNB cav = (CAVWNB) base;
                featureEvidence = buildCavwnbEvidence(cav, disc, header);
                calculationMethod = "类×属性值权重 × 对数条件概率（weight × log P(x|c)，非归一化）";
            } else if (base instanceof MVCAVWNB) {
                MVCAVWNB mv = (MVCAVWNB) base;
                views.put(viewObj("原始属性视图", mv.classifier_view1.distributionForInstance(disc), header));
                views.put(viewObj("SPODE 标签视图", mv.distributionForInstance_SPODE_Label(disc), header));
                views.put(viewObj("RT 标签视图", mv.distributionForInstance_RT_Label(disc), header));
                double third = 1.0 / 3.0;
                viewWeights.put(third).put(third).put(third);
                if (mv.classifier_view1 instanceof CAVWNB) {
                    featureEvidence = buildCavwnbEvidence((CAVWNB) mv.classifier_view1, disc, header);
                }
                calculationMethod = "类×属性值权重 × 对数条件概率（weight × log P(x|c)，非归一化）";
            } else if (base instanceof EMAWNB) {
                EMAWNB ema = (EMAWNB) base;
                ema.LearningViewWweight(disc);
                views.put(viewObj("原始属性视图", ema.distributionForInstance1(disc), header));
                views.put(viewObj("SPODE 标签视图", ema.distributionForInstance2(disc), header));
                views.put(viewObj("RT 标签视图", ema.distributionForInstance3(disc), header));
                viewWeights.put(round(ema.w_view1)).put(round(ema.w_view2)).put(round(ema.w_view3));
                if (ema.classifier_view1 instanceof CAVWNB) {
                    featureEvidence = buildCavwnbEvidence((CAVWNB) ema.classifier_view1, disc, header);
                }
                calculationMethod = "类×属性值权重 × 对数条件概率（weight × log P(x|c)，非归一化）";
            } else if (base instanceof DIWNB_HE) {
                // 双视图：原始视图 + 生成视图（KNN 生成）
                DIWNB_HE diwnb = (DIWNB_HE) base;
                views.put(viewObj("原始视图", diwnb.distributionForView1(disc), header));
                views.put(viewObj("生成视图", diwnb.distributionForView2(disc), header));
                double[] vw = diwnb.getViewWeightsForReport();
                viewWeights.put(round(vw[0])).put(round(vw[1]));
            } else if (base instanceof A2WNB) {
                // 增广单视图，无独立视图；特征证据暂未接入
            }

            explain.put("views", views);
            explain.put("view_weights", viewWeights);
            explain.put("feature_evidence", featureEvidence);
            if (calculationMethod != null) {
                explain.put("calculation_method", calculationMethod);
            }
        } catch (Exception ignored) {
            // 解释提取失败不阻断预测，返回空解释
        }
        return explain;
    }

    private static JSONObject viewObj(String name, double[] dist, Instances header) {
        JSONObject obj = new JSONObject().put("name", name);
        JSONArray arr = new JSONArray();
        int argmax = 0;
        for (int i = 1; i < dist.length; i++) {
            if (dist[i] > dist[argmax]) argmax = i;
        }
        for (int i = 0; i < dist.length; i++) {
            arr.put(new JSONObject().put("class", header.classAttribute().value(i))
                    .put("probability", round(dist[i])));
        }
        obj.put("predicted_label", header.classAttribute().value(argmax));
        return obj.put("distribution", arr);
    }

    /** 提取 CAVWNB 每个特征值对各风险类的加权条件概率贡献。 */
    private static JSONArray buildCavwnbEvidence(CAVWNB cav, Instance disc, Instances header) throws Exception {
        WANBDistribution wd = cav.geDistribution();
        if (wd == null) {
            return new JSONArray();
        }
        double[] weights = wd.getWeights();       // 长度 = attrValueCounts * numClasses
        int[] card = wd.getCardinalities();       // 每个属性的取值数
        int[] offset = wd.getOffset();            // 每个属性在权重数组中的偏移
        double[][][] theta = wd.getThetaUC();     // n x nc x card[u]，条件概率 P(x_u|class)
        int attrValueCounts = wd.getAttValueCounts();
        int nc = theta[0].length;

        JSONArray arr = new JSONArray();
        for (int u = 0; u < card.length; u++) {
            if (disc.isMissing(u)) {
                continue;
            }
            int v = (int) disc.value(u);
            if (v < 0 || v >= card[u]) {
                continue;
            }
            JSONObject feat = new JSONObject();
            feat.put("attribute", disc.attribute(u).name());
            feat.put("value", disc.attribute(u).value(v));
            feat.put("view", "原始属性视图");
            JSONArray contribs = new JSONArray();
            for (int c = 0; c < nc; c++) {
                double w = weights[attrValueCounts * c + offset[u] + v];
                double p = theta[u][c][v];
                double logp = Math.log(Math.max(p, 1e-75));
                contribs.put(new JSONObject()
                        .put("class", header.classAttribute().value(c))
                        .put("weight", round(w))
                        .put("cond_prob", round(p))
                        .put("contribution", round(w * logp)));
            }
            feat.put("class_contributions", contribs);
            arr.put(feat);
        }
        return arr;
    }

    private static void handleShutdown(HttpExchange ex) throws IOException {
        respond(ex, 200, new JSONObject().put("status", "stopping"));
        new Thread(() -> System.exit(0), "nb-shutdown").start();
    }

    private static Instances loadDataset(String path) throws Exception {
        Instances data = new DataSource(path).getDataSet();
        if (data == null || data.numAttributes() < 2) throw new IllegalArgumentException("数据集字段不足");
        if (data.classIndex() < 0) data.setClassIndex(data.numAttributes() - 1);
        data.deleteWithMissingClass();
        if (!data.classAttribute().isNominal()) throw new IllegalArgumentException("分类标签必须是名义型字段");
        return data;
    }

    private static Classifier createClassifier(JSONObject parameters) throws Exception {
        Classifier base = (Classifier) Class.forName(classNameFor(algorithmCode)).getDeclaredConstructor().newInstance();
        applyAlgorithmParameters(base, parameters);
        // 原始研究算法按离散属性工作；FilteredClassifier 使其可以训练平台中的数值数据，
        // 同时把 schema 中的离散化参数真正应用到训练数据。
        return new FilteredClassifierWithDiscretize(base, parameters);
    }

    private static void applyAlgorithmParameters(Classifier base, JSONObject parameters) throws Exception {
        if (base instanceof CAVWNB) {
            CAVWNB cav = (CAVWNB) base;
            if (parameters.has("objective")) cav.setObjectiveFunction(parameters.getString("objective"));
            if (parameters.has("regularizer")) cav.setRegularizer(parameters.getString("regularizer"));
            if (parameters.has("regularization_lambda")) {
                cav.setRegularizationLambda(parameters.getDouble("regularization_lambda"));
            }
        } else if (base instanceof A2WNB) {
            A2WNB a2 = (A2WNB) base;
            if (parameters.has("rode_task")) {
                Classifier first = a2.getClassifier();
                if (!(first instanceof RODE)) {
                    throw new IllegalArgumentException("A2WNB 的第一阶段分类器必须是 RODE");
                }
                ((RODE) first).setTask(parameters.getInt("rode_task"));
            }
        }
    }

    private static Instance buildInstance(Instances header, JSONObject features) {
        DenseInstance instance = new DenseInstance(header.numAttributes());
        instance.setDataset(header);
        int classIndex = header.classIndex();
        for (int i = 0; i < header.numAttributes(); i++) {
            if (i == classIndex) { instance.setMissing(i); continue; }
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
                } else {
                    String label = String.valueOf(value);
                    if (attr.indexOfValue(label) >= 0) instance.setValue(i, label);
                    else instance.setMissing(i);
                }
            } catch (Exception ignored) { instance.setMissing(i); }
        }
        return instance;
    }

    private static int countClass(Instances data, int classIndex) {
        int count = 0;
        for (int i = 0; i < data.numInstances(); i++) if ((int) data.instance(i).classValue() == classIndex) count++;
        return count;
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

    /** Applies configurable numeric discretization before the research classifier. */
    private static final class FilteredClassifierWithDiscretize extends FilteredClassifier {
        private static final long serialVersionUID = 1L;
        FilteredClassifierWithDiscretize(Classifier base, JSONObject parameters) throws Exception {
            setClassifier(base);
            Discretize discretize = new Discretize();
            discretize.setUseBinNumbers(true);
            if (parameters.has("discrete_bins")) {
                discretize.setBins(parameters.getInt("discrete_bins"));
            }
            if (parameters.has("discrete_method")) {
                String method = parameters.getString("discrete_method");
                discretize.setUseEqualFrequency("equal_freq".equalsIgnoreCase(method));
            }
            setFilter(discretize);
        }
    }
}
