package weka.classifiers.zh.KFDB;

import KFDB.wdBayesOnlinePYP;
import weka.core.Capabilities;
import weka.core.CapabilitiesHandler;
import weka.core.Instance;

/**
 * KFDB（K-Free Dependence Bayesian Classifier）平台适配器。
 *
 * 算法主体直接复用作者仓库的 KFDB.wdBayesOnlinePYP：
 *   - buildClassifier(Instances) 先把数据写成临时 ARFF，再学习依赖结构与概率参数；
 *   - distributionForInstance(Instance) 给出类别后验分布。
 *
 * 原实现有两处不符合 Weka 通用分类器契约，会让平台外层的
 * FilteredClassifier（负责前置离散化）失效，这里只做最小修补：
 *   1. getCapabilities() 返回 null → FilteredClassifier.getCapabilities() 空指针；
 *   2. classifyInstance() 恒返回 0 → 走 classifyInstance 的评估路径全部判成第一类。
 * 结构学习 / 概率估计 / 预测逻辑未做任何改动。
 */
public class KFDB extends wdBayesOnlinePYP implements CapabilitiesHandler {
    private static final long serialVersionUID = 1L;

    /** 记录用户配置的父属性上限，供平台解释接口只读展示（算法内部仍用 setK 的值）。 */
    private int m_MaxParentsForReport = 1;

    @Override
    public void setK(int k) {
        super.setK(k);
        m_MaxParentsForReport = k;
    }

    public int getMaxParentsForReport() {
        return m_MaxParentsForReport;
    }

    @Override
    public Capabilities getCapabilities() {
        Capabilities capabilities = new Capabilities(this);
        capabilities.enableAll();
        return capabilities;
    }

    @Override
    public double classifyInstance(Instance instance) throws Exception {
        double[] distribution = distributionForInstance(instance);
        int best = 0;
        for (int i = 1; i < distribution.length; i++) {
            if (distribution[i] > distribution[best]) {
                best = i;
            }
        }
        return best;
    }
}
