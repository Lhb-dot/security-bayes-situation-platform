package weka.classifiers.trees;

import weka.classifiers.AbstractClassifier;
import weka.core.Instance;
import weka.core.Instances;
import weka.core.Utils;

/**
 * Compatibility implementation for MVCAVWNB's RandomForest2 extension API.
 * The supplied source expects per-attribute probability helpers that are not
 * part of standard Weka. Standard Weka RandomForest provides the real forest
 * prediction; these helpers expose that prediction in the shape expected by
 * the MVCAVWNB view transformation.
 */
public class RandomForest2 extends AbstractClassifier {
    private static final long serialVersionUID = 1L;
    private final weka.classifiers.trees.RandomForest forest = new weka.classifiers.trees.RandomForest();
    private int numAttributes;

    public RandomForest2(int numAttributes) {
        this.numAttributes = Math.max(1, numAttributes);
        forest.setNumIterations(50);
        forest.setSeed(1);
    }

    @Override
    public void buildClassifier(Instances data) throws Exception {
        numAttributes = Math.max(1, data.numAttributes() - 1);
        forest.buildClassifier(data);
    }

    @Override
    public double[] distributionForInstance(Instance instance) throws Exception {
        return forest.distributionForInstance(instance);
    }

    public String[] distributionForInstance1(Instance instance) throws Exception {
        double[] distribution = distributionForInstance(instance);
        String label = String.valueOf(Utils.maxIndex(distribution));
        String[] result = new String[numAttributes];
        for (int i = 0; i < result.length; i++) result[i] = label;
        return result;
    }

    public double[] distributionForInstance2(Instance instance) throws Exception {
        double[] distribution = distributionForInstance(instance);
        double[] result = new double[numAttributes * distribution.length];
        for (int i = 0; i < numAttributes; i++) {
            System.arraycopy(distribution, 0, result, i * distribution.length, distribution.length);
        }
        return result;
    }

    public void distributionForInstance_c_p(Instance instance, String[] predLabel, double[][] probs) throws Exception {
        double[] distribution = distributionForInstance(instance);
        if (predLabel != null && predLabel.length > 0) predLabel[0] = String.valueOf(Utils.maxIndex(distribution));
        if (probs != null && probs.length > 0) {
            for (int i = 0; i < probs.length; i++) {
                if (probs[i] == null || probs[i].length < distribution.length) probs[i] = new double[distribution.length];
                System.arraycopy(distribution, 0, probs[i], 0, distribution.length);
            }
        }
    }

    public void distributionForInstance_c_p_x(Instance instance, String[] predLabel, double[][] probs, int numGroups) throws Exception {
        distributionForInstance_c_p(instance, predLabel, probs);
    }

    public String getTreesDetails() { return forest.toString(); }
}
