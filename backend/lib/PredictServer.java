import com.sun.net.httpserver.HttpExchange;
import com.sun.net.httpserver.HttpServer;

import java.io.IOException;
import java.io.OutputStream;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.Executors;

import org.json.JSONArray;
import org.json.JSONObject;

import weka.classifiers.Classifier;
import weka.classifiers.bayes.PMWNB.PMWNB.PMWNB;
import weka.classifiers.bayes.PMWNB.CAVWNB.CAVWNB;
import weka.classifiers.bayes.PMWNB.CAVWNB.WANBDistribution;
import weka.core.Attribute;
import weka.core.DenseInstance;
import weka.core.Instance;
import weka.core.Instances;
import weka.core.SerializationHelper;
import weka.core.converters.ConverterUtils.DataSource;

/**
 * 通用 PMWNB 预测服务（独立小服务）。
 *
 * 解决旧 /predict 写死 flowLength/duration/accessFreq 三个特征的问题：
 * 这里按数据集 ARFF 头读取完整字段结构，再按字段名把 input_features 填成完整实例，
 * 交给反序列化出来的 PMWNB 模型 distributionForInstance 预测。
 *
 * 接口：
 *   GET  /health  -> {"status":"ok","model_cache":N,"header_cache":N}
 *   POST /predict -> body {"model_path","arff_path","features":{...}}
 *                    resp {"success":true,"data":{"prediction_label","probability",
 *                          "class_distribution":[{class,probability}]}}
 */
public class PredictServer {

    private static final ConcurrentHashMap<String, Classifier> MODEL_CACHE = new ConcurrentHashMap<>();
    private static final ConcurrentHashMap<String, Instances> HEADER_CACHE = new ConcurrentHashMap<>();

    public static void main(String[] args) throws Exception {
        int port = args.length > 0 ? Integer.parseInt(args[0]) : 12314;
        HttpServer server = HttpServer.create(new InetSocketAddress("127.0.0.1", port), 0);
        server.createContext("/health", PredictServer::handleHealth);
        server.createContext("/predict", PredictServer::handlePredict);
        server.setExecutor(Executors.newFixedThreadPool(4));
        server.start();
        System.out.println("[PredictServer] listening on 127.0.0.1:" + port);
    }

    private static void handleHealth(HttpExchange ex) throws IOException {
        JSONObject body = new JSONObject()
                .put("status", "ok")
                .put("model_cache", MODEL_CACHE.size())
                .put("header_cache", HEADER_CACHE.size());
        respond(ex, 200, body);
    }

    private static void handlePredict(HttpExchange ex) throws IOException {
        if (!"POST".equalsIgnoreCase(ex.getRequestMethod())) {
            respond(ex, 405, new JSONObject().put("success", false).put("error", "Method Not Allowed"));
            return;
        }
        try {
            JSONObject req = new JSONObject(readBody(ex));
            String modelPath = req.getString("model_path");
            String arffPath = req.getString("arff_path");
            JSONObject features = req.optJSONObject("features");
            if (features == null) {
                throw new IllegalArgumentException("缺少 features 字段");
            }

            Classifier clf = loadModel(modelPath);
            Instances header = loadHeader(arffPath);

            Instance inst = buildInstance(header, features);
            double[] dist = clf.distributionForInstance(inst);

            int argmax = 0;
            for (int i = 1; i < dist.length; i++) {
                if (dist[i] > dist[argmax]) argmax = i;
            }
            String label = header.classAttribute().value(argmax);
            double probability = dist[argmax];

            JSONArray classes = new JSONArray();
            for (int i = 0; i < dist.length; i++) {
                classes.put(new JSONObject()
                        .put("class", header.classAttribute().value(i))
                        .put("probability", dist[i]));
            }

            JSONObject data = new JSONObject()
                    .put("prediction_label", label)
                    .put("probability", probability)
                    .put("class_distribution", classes);
            JSONObject explain = buildExplain(clf, inst, header);
            data.put("views", explain.getJSONArray("views"));
            data.put("view_weights", explain.getJSONArray("view_weights"));
            data.put("feature_evidence", explain.getJSONArray("feature_evidence"));
            if (explain.has("calculation_method")) {
                data.put("calculation_method", explain.getString("calculation_method"));
            }
            respond(ex, 200, new JSONObject().put("success", true).put("data", data));
        } catch (Exception e) {
            JSONObject err = new JSONObject().put("success", false)
                    .put("error", String.valueOf(e.getMessage()));
            respond(ex, 500, err);
        }
    }

    /** 组装 PMWNB 可解释性信息：双视图预测 + 特征加权条件概率（6.6.2 统一解释输出）。 */
    private static JSONObject buildExplain(Classifier clf, Instance instance, Instances header) {
        JSONObject explain = new JSONObject();
        explain.put("views", new JSONArray());
        explain.put("view_weights", new JSONArray());
        explain.put("feature_evidence", new JSONArray());
        try {
            if (!(clf instanceof PMWNB)) {
                return explain;
            }
            PMWNB pm = (PMWNB) clf;
            JSONArray views = new JSONArray();
            views.put(viewObj("EWD 基础视图", pm.distributionForView1(instance), header));
            views.put(viewObj("MDLP 基础视图", pm.distributionForView2(instance), header));
            explain.put("views", views);
            explain.put("view_weights", new JSONArray().put(0.5).put(0.5));
            explain.put("feature_evidence", buildCavwnbEvidence(
                    pm.getView1BaseCAVWNB(), pm.toView1(instance), header));
            explain.put("calculation_method", "类×属性值权重 × 对数条件概率（weight × log P(x|c)，非归一化）");
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

    private static JSONArray buildCavwnbEvidence(CAVWNB cav, Instance disc, Instances header) throws Exception {
        if (cav == null) {
            return new JSONArray();
        }
        WANBDistribution wd = cav.geDistribution();
        if (wd == null) {
            return new JSONArray();
        }
        double[] weights = wd.getWeights();
        int[] card = wd.getCardinalities();
        int[] offset = wd.getOffset();
        double[][][] theta = wd.getThetaUC();
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
            feat.put("view", "EWD 基础视图");
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

    private static double round(double value) {
        return Math.round(value * 10000.0) / 10000.0;
    }

    private static Classifier loadModel(String modelPath) throws Exception {
        return MODEL_CACHE.computeIfAbsent(modelPath, p -> {
            try {
                return (Classifier) SerializationHelper.read(p);
            } catch (Exception e) {
                throw new RuntimeException("模型加载失败: " + e.getMessage(), e);
            }
        });
    }

    /** 只读 ARFF 头部结构（不加载数据行），class 索引取最后一列（与训练 loadDataset 一致）。 */
    private static Instances loadHeader(String arffPath) throws Exception {
        return HEADER_CACHE.computeIfAbsent(arffPath, p -> {
            try {
                Instances header = new DataSource(p).getStructure();
                if (header.classIndex() < 0) {
                    header.setClassIndex(header.numAttributes() - 1);
                }
                return header;
            } catch (Exception e) {
                throw new RuntimeException("ARFF 头解析失败: " + e.getMessage(), e);
            }
        });
    }

    private static Instance buildInstance(Instances header, JSONObject features) {
        DenseInstance inst = new DenseInstance(header.numAttributes());
        inst.setDataset(header);
        int classIdx = header.classIndex();
        for (int i = 0; i < header.numAttributes(); i++) {
            if (i == classIdx) {
                inst.setMissing(i);
                continue;
            }
            Attribute attr = header.attribute(i);
            String name = attr.name();
            if (!features.has(name)) {
                inst.setMissing(i);
                continue;
            }
            Object val = features.get(name);
            if (val == null || JSONObject.NULL.equals(val) || "".equals(String.valueOf(val))) {
                inst.setMissing(i);
                continue;
            }
            try {
                if (attr.isNumeric()) {
                    double d = val instanceof Number ? ((Number) val).doubleValue()
                            : Double.parseDouble(String.valueOf(val).trim());
                    inst.setValue(i, d);
                } else {
                    inst.setValue(i, String.valueOf(val));
                }
            } catch (Exception ignored) {
                inst.setMissing(i);
            }
        }
        return inst;
    }

    private static String readBody(HttpExchange ex) throws IOException {
        byte[] bytes = ex.getRequestBody().readAllBytes();
        return new String(bytes, StandardCharsets.UTF_8);
    }

    private static void respond(HttpExchange ex, int code, JSONObject body) throws IOException {
        byte[] bytes = body.toString().getBytes(StandardCharsets.UTF_8);
        ex.getResponseHeaders().set("Content-Type", "application/json; charset=utf-8");
        ex.sendResponseHeaders(code, bytes.length);
        try (OutputStream os = ex.getResponseBody()) {
            os.write(bytes);
        }
    }
}
