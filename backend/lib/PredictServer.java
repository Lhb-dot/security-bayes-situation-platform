import com.sun.net.httpserver.HttpExchange;
import com.sun.net.httpserver.HttpServer;

import java.io.File;
import java.io.IOException;
import java.io.OutputStream;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.util.Collections;
import java.util.Iterator;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.Executors;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashSet;
import java.util.Set;

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

    /**
     * 模型缓存预算（字节）。
     *
     * 原来按条目数限制（capacity=4），但模型大小差三个数量级 —— 实测同目录下
     * 47.5 / 98.6 / 123.5 / 178.9 / 205.6 MB 各一份，反序列化后按 1.4 倍膨胀，
     * 4 个"条目"最坏情况是 1.15 GB，-Xmx384m 必然 OutOfMemoryError。
     * 上限必须按字节算。
     *
     * 默认取堆上限的 55%，可用 -Dpredict.modelCacheBudgetBytes 覆盖。
     */
    private static final long MODEL_CACHE_BUDGET_BYTES = Long.getLong(
            "predict.modelCacheBudgetBytes",
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
     * 而是把缓存清空后单独放它 —— 实测 205 MB 模型占 287 MB 堆，-Xmx384m 装得下。
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
                System.out.println("[PredictServer] 缓存预算不足，淘汰最久未使用的模型: " + eldest.getKey());
            }
        }
    }

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

    private static void handleHealth(HttpExchange ex) {
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
            JSONObject explain = buildExplain(clf, inst, header, req.optJSONArray("risk_labels"));
            data.put("views", explain.getJSONArray("views"));
            data.put("view_weights", explain.getJSONArray("view_weights"));
            data.put("feature_evidence", explain.getJSONArray("feature_evidence"));
            data.put("algorithm_details", explain.getJSONObject("algorithm_details"));
            if (explain.has("calculation_method")) {
                data.put("calculation_method", explain.getString("calculation_method"));
            }
            try {
                data.put("feature_attribution", buildFeatureAttribution(clf, inst, header, features));
            } catch (Exception ignored) {
                data.put("feature_attribution", new JSONArray());
            }
            respond(ex, 200, new JSONObject().put("success", true).put("data", data));
        } catch (Throwable e) {
            // 必须是 Throwable 而不是 Exception：OutOfMemoryError 继承自 Error，
            // catch (Exception) 接不住它，响应永远不发，客户端只能等到自己的超时。
            JSONObject err = new JSONObject().put("success", false)
                    .put("error", message(e));
            respond(ex, 500, err);
        }
    }

    /** 组装 PMWNB 可解释性信息：双基础视图、十个子模型和特征证据。 */
    private static JSONObject buildExplain(
            Classifier clf, Instance instance, Instances header, JSONArray riskLabels) {
        JSONObject explain = new JSONObject();
        explain.put("views", new JSONArray());
        explain.put("view_weights", new JSONArray());
        explain.put("feature_evidence", new JSONArray());
        explain.put("algorithm_details", new JSONObject()
                .put("algorithm_code", "PMWNB")
                .put("specific", unavailable("PMWNB 专属解释提取失败"))
                .put("availability", unavailable("PMWNB 专属解释提取失败")));
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
            JSONArray submodels = new JSONArray();
            double[][] probabilities = pm.distributionForSubmodels(instance);
            String[] names = {
                    "EWD 原始属性视图", "EWD SPODE 标签视图", "EWD SPODE 概率视图",
                    "EWD RF 标签视图", "EWD RF 概率视图", "MDLP 原始属性视图",
                    "MDLP SPODE 标签视图", "MDLP SPODE 概率视图", "MDLP RF 标签视图",
                    "MDLP RF 概率视图"
            };
            for (int i = 0; i < probabilities.length; i++) {
                submodels.put(viewObj(names[i], probabilities[i], header));
            }
            int riskSupport = 0;
            Set<String> labels = new HashSet<>();
            for (int i = 0; i < submodels.length(); i++) {
                JSONObject item = submodels.getJSONObject(i);
                String label = item.optString("predicted_label", "");
                labels.add(label);
                if (isRiskLabel(label, riskLabels)) riskSupport++;
            }
            JSONObject specific = new JSONObject()
                    .put("submodels", submodels)
                    .put("risk_support_count", riskLabels == null ? JSONObject.NULL : riskSupport)
                    .put("disagreement", new JSONObject()
                            .put("has_conflict", labels.size() > 1)
                            .put("distinct_label_count", labels.size()))
                    .put("available", true);
            explain.put("algorithm_details", new JSONObject()
                    .put("algorithm_code", "PMWNB")
                    .put("specific", specific)
                    .put("availability", new JSONObject().put("available", true).put("reason", JSONObject.NULL)));
            explain.put("calculation_method", "类×属性值权重 × 对数条件概率（weight × log P(x|c)，非归一化）");
        } catch (Exception ignored) {
            // 解释提取失败不阻断预测，返回空解释
        }
        return explain;
    }

    private static JSONObject unavailable(String reason) {
        return new JSONObject().put("available", false).put("reason", reason);
    }

    private static boolean isRiskLabel(String label, JSONArray riskLabels) {
        if (riskLabels == null) return false;
        for (int i = 0; i < riskLabels.length(); i++) {
            if (label.equals(String.valueOf(riskLabels.opt(i)))) return true;
        }
        return false;
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

    /** Read-only local sensitivity diagnostic; it does not change model inference. */
    private static JSONArray buildFeatureAttribution(
            Classifier classifier, Instance instance, Instances header, JSONObject features) throws Exception {
        double[] original = classifier.distributionForInstance(instance);
        int predicted = 0;
        for (int i = 1; i < original.length; i++) if (original[i] > original[predicted]) predicted = i;
        ArrayList<JSONObject> items = new ArrayList<>();
        for (int i = 0; i < header.numAttributes(); i++) {
            if (i == header.classIndex() || instance.isMissing(i)) continue;
            Instance masked = new DenseInstance(instance);
            masked.setDataset(header);
            masked.setMissing(i);
            double[] changed = classifier.distributionForInstance(masked);
            double delta = original[predicted] - changed[predicted];
            Attribute attr = header.attribute(i);
            Object raw = features.has(attr.name()) ? features.get(attr.name()) : JSONObject.NULL;
            String processed = attr.isNominal() ? instance.stringValue(i) : String.valueOf(instance.value(i));
            items.add(new JSONObject()
                    .put("feature_name", attr.name())
                    .put("raw_value", raw)
                    .put("processed_value", processed)
                    .put("contribution", round(Math.abs(delta)))
                    .put("signed_contribution", round(delta))
                    .put("supports_predicted", delta >= 0));
        }
        items.sort(Comparator.comparingDouble(x -> -x.optDouble("contribution", 0.0)));
        JSONArray result = new JSONArray();
        int limit = Math.min(10, items.size());
        for (int i = 0; i < limit; i++) result.put(items.get(i).put("rank", i + 1));
        return result;
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

    private static String message(Throwable e) {
        return e.getMessage() == null ? e.toString() : e.getMessage();
    }

    /**
     * 读取模型，命中缓存则直接返回；未命中先按预算腾出空间，再反序列化。
     *
     * 刻意不用 computeIfAbsent：缓存是 synchronizedMap，其 computeIfAbsent 会在持锁期间
     * 执行反序列化（几百 MB、数百毫秒），把其它模型的读取一起堵住。
     *
     * **淘汰必须在反序列化之前**：如果等 put 时再淘汰，新模型已经在堆里了，
     * 新旧两份同时存活，照样 OOM。
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

    /**
     * 写回响应。
     *
     * **刻意吞掉 IOException**：客户端提前断开时 `sendResponseHeaders` /
     * `getResponseBody` 会抛 IOException，而 `handlePredict` 的 catch 块里那次
     * `respond` 不在任何 try 内 —— 异常逃出去会直接打死工作线程，
     * `ThreadPoolExecutor` 只会补一个新线程，客户端永远拿不到响应
     * （实测线程编号一路涨到 9，即死了 5 次）。响应通道坏了没有任何补救手段，
     * 唯一正确的处理就是别把线程一起带走。
     */
    private static void respond(HttpExchange ex, int code, JSONObject body) {
        try {
            byte[] bytes = body.toString().getBytes(StandardCharsets.UTF_8);
            ex.getResponseHeaders().set("Content-Type", "application/json; charset=utf-8");
            ex.sendResponseHeaders(code, bytes.length);
            try (OutputStream os = ex.getResponseBody()) {
                os.write(bytes);
            }
        } catch (IOException e) {
            System.err.println("[PredictServer] 响应写回失败（客户端可能已断开）: " + e);
        }
    }
}
