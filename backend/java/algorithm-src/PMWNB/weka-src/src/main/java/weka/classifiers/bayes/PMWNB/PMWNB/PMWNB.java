package weka.classifiers.bayes.PMWNB.PMWNB;

import weka.classifiers.AbstractClassifier;
import weka.core.Instance;
import weka.core.Instances;
import weka.core.Utils;
import weka.filters.Filter;

/** Perturbation-driven Matrix-view Weighted Naive Bayes */
public class PMWNB extends AbstractClassifier {

	/**
	 * The first row of the view matrix:
	 * an ensemble of CAVWNB models built on the first base view and its four latent
	 * views.
	 */
	private PMWNB_L view1 = new PMWNB_L();

	/**
	 * The second row of the view matrix:
	 * an ensemble of CAVWNB models built on the second base view and its four
	 * latent views.
	 */
	private PMWNB_L view2 = new PMWNB_L();

	private int numClasses;

	private int numAttrs;

	private int numInstances;

	/** The first unsupervised perturbation strategy */
	private weka.filters.unsupervised.attribute.Discretize view1_Discretizor;

	/** The second supervised perturbation strategy */
	private weka.filters.supervised.attribute.Discretize view2_Discretizor;

	/** The first base view */
	Instances view1_data;

	/** The second base view */
	Instances view2_data;

	@Override
	public void buildClassifier(Instances data) throws Exception {

		numAttrs = data.numAttributes() - 1;
		numClasses = data.numClasses();
		numInstances = data.numInstances();

		/** Apply two perturbation strategies on raw attributes */
		view1_Discretizor = new weka.filters.unsupervised.attribute.Discretize();
		view2_Discretizor = new weka.filters.supervised.attribute.Discretize();

		view1_Discretizor.setInputFormat(data);
		view2_Discretizor.setInputFormat(data);

		view1_Discretizor.setBins(10);

		/** Construct the first and second base view */
		view1_data = Filter.useFilter(data, view1_Discretizor);
		view2_data = Filter.useFilter(data, view2_Discretizor);

		view1.setFilterIsSupervised(false);
		view2.setFilterIsSupervised(true);

		/**
		 * For each base view, generate four latent views and
		 * construct the corresponding ensemble CAVWNB models.
		 */
		view1.buildClassifier(view1_data);
		view2.buildClassifier(view2_data);

	}

	public double[] distributionForInstance(Instance instance) throws Exception {
		double[] result = new double[numClasses];

		/** Map the test instance to the representation in the first base view */
		view1_Discretizor.input(instance);
		Instance predData_view1 = view1_Discretizor.output();

		/**
		 * Summation of the class-membership probabilities from models
		 * in the first line of matrix-view
		 */
		double[] view1_probs = view1.distributionForInstance5(predData_view1);

		/** map the test instance into the representation in the second base view */
		view2_Discretizor.input(instance);
		Instance predData_view2 = view2_Discretizor.output();

		/**
		 * Summation of the class-membership probabilities from models
		 * in the second line of matrix-view
		 */
		double[] view2_probs = view2.distributionForInstance5(predData_view2);

		/** The final class-membership probabilities for classification */
		for (int i = 0; i < numClasses; i++) {
			result[i] += view1_probs[i];
			result[i] += view2_probs[i];
		}
		Utils.normalize(result);

		return result;

	}

	/** 第一行视图（EWD 基础视图 + 4 个潜在视图）的融合后验概率（供可解释性展示，归一化）。 */
	public double[] distributionForView1(Instance instance) throws Exception {
		view1_Discretizor.input(instance);
		Instance d = view1_Discretizor.output();
		double[] probs = view1.distributionForInstance5(d);
		Utils.normalize(probs);
		return probs;
	}

	/** 第二行视图（MDLP 基础视图 + 4 个潜在视图）的融合后验概率（供可解释性展示，归一化）。 */
	public double[] distributionForView2(Instance instance) throws Exception {
		view2_Discretizor.input(instance);
		Instance d = view2_Discretizor.output();
		double[] probs = view2.distributionForInstance5(d);
		Utils.normalize(probs);
		return probs;
	}

	/** 第一行视图的基础 CAVWNB 模型（供特征加权条件概率提取）。 */
	public weka.classifiers.bayes.PMWNB.CAVWNB.CAVWNB getView1BaseCAVWNB() {
		return view1.classifier_view1;
	}

	/** 把原始实例映射到第一行（EWD）视图表示（供特征证据提取）。 */
	public Instance toView1(Instance instance) throws Exception {
		view1_Discretizor.input(instance);
		return view1_Discretizor.output();
	}

	public static void main(String[] args) {
		runClassifier(new PMWNB(), args);
	}

}
