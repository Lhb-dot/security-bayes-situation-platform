package weka.classifiers.zh.FLNB;

import weka.classifiers.AbstractClassifier;
import weka.classifiers.Classifier;
import weka.classifiers.bayes.FLNB_log;
import weka.classifiers.bayes.FLNB_poly;
import weka.core.Capabilities;
import weka.core.Instance;
import weka.core.Instances;

/**
 * FLNB（Frequency-based Lazy Naive Bayes）平台适配器。
 *
 * 作者仓库提供两个相似度加权版本，由 weight_scheme 参数选择：
 *   - poly：多项式相似度（FLNB_poly，默认）
 *   - log ：对数相似度（FLNB_log）
 *
 * 两个版本都按离散属性工作（源码里把属性值直接当整数下标使用），
 * 数值特征由平台外层的 FilteredClassifier 先做 Weka 离散化。
 * 这里不做任何算法改动，只按参数把请求转发给对应实现。
 */
public class FLNB extends AbstractClassifier {
    private static final long serialVersionUID = 1L;

    private final FLNB_poly m_Poly = new FLNB_poly();
    private final FLNB_log m_Log = new FLNB_log();
    private String m_WeightScheme = "poly";

    public void setWeightScheme(String scheme) {
        m_WeightScheme = "log".equalsIgnoreCase(scheme) ? "log" : "poly";
    }

    public String getWeightScheme() {
        return m_WeightScheme;
    }

    private Classifier delegate() {
        return "log".equals(m_WeightScheme) ? m_Log : m_Poly;
    }

    @Override
    public void buildClassifier(Instances data) throws Exception {
        delegate().buildClassifier(data);
    }

    @Override
    public double[] distributionForInstance(Instance instance) throws Exception {
        return delegate().distributionForInstance(instance);
    }

    @Override
    public double classifyInstance(Instance instance) throws Exception {
        return delegate().classifyInstance(instance);
    }

    @Override
    public Capabilities getCapabilities() {
        Capabilities capabilities = new Capabilities(this);
        capabilities.enableAll();
        return capabilities;
    }
}
