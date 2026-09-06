package weka.classifiers.bayes.PMWNB.PMWNB;

import weka.classifiers.AbstractClassifier;
import weka.classifiers.trees.RandomForest2;
import weka.core.Instance;
import weka.core.Instances;

public class RF_m extends AbstractClassifier {

	private static final long serialVersionUID = 1L;

	private RandomForest2 rf = null;

	public void buildClassifier(Instances data) throws Exception {
		rf = new RandomForest2(data.numAttributes() - 1);
		rf.buildClassifier(data);
	}

	public double[] distributionForInstance(Instance instance) throws Exception {
		return rf.distributionForInstance(instance);
	}

	public static void main(String[] args) {
		runClassifier(new RF_m(), args);
	}

	public void distributionForInstance_c_p(Instance instance, String[] pred_label, double[][] probs) throws Exception {
		rf.distributionForInstance_c_p(instance, pred_label, probs);
	}

}
