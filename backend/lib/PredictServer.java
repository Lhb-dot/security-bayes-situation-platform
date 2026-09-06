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
            respond(ex, 200, new JSONObject().put("success", true).put("data", data));
        } catch (Exception e) {
            JSONObject err = new JSONObject().put("success", false)
                    .put("error", String.valueOf(e.getMessage()));
            respond(ex, 500, err);
        }
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
