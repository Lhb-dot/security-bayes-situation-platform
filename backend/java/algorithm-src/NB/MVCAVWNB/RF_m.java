package weka.classifiers.zh.MVCAVWNB;

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

	public void distributionForInstance_c_p_x(Instance instance, String[] pred_label, double[][] probs, int numGroups)
			throws Exception {
		rf.distributionForInstance_c_p_x(instance, pred_label, probs, numGroups);
	}

	public String[] distributionForInstance1(Instance instance) throws Exception {
		return rf.distributionForInstance1(instance);
	}

	/**
	 * m * RF 各自的结果
	 */
	public double[] distributionForInstance2(Instance instance) throws Exception {
		return rf.distributionForInstance2(instance);
	}
	
	public String getTreesDetails() {
		if (rf == null) return "RF_m is not built yet (rf is null).";
		return rf.getTreesDetails();
	}
	
	

}
