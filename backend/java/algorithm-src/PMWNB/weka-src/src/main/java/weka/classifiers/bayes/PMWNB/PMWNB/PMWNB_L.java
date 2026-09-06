package weka.classifiers.bayes.PMWNB.PMWNB;

import weka.classifiers.AbstractClassifier;
import weka.classifiers.Classifier;
import weka.classifiers.bayes.PMWNB.CAVWNB.CAVWNB;
import weka.classifiers.bayes.PMWNB.PMWNB.RF_m;
import weka.classifiers.bayes.PMWNB.PMWNB.SPODE;
import weka.core.Attribute;
import weka.core.FastVector;
import weka.core.Instance;
import weka.core.Instances;
import weka.core.Utils;

import weka.estimators.DiscreteEstimator;
import weka.filters.Filter;
import weka.filters.supervised.attribute.Discretize;

/** The ensemble models built upon in a line of matrix-view */
public class PMWNB_L extends AbstractClassifier {

	/** ---------------------- BASE CLASSIFIERS --------------------------- */
	/** The ensemble SPODEs */
	public SPODE baseClassifier_S = new SPODE();
	/** The ensemble RTs */
	public RF_m baseClassifier_R = new RF_m();

	/** --------------------- FOUR LATENT VIEWS -------------------------- */
	/** The first label view */
	Instances viewSL;

	/** The first probability view */
	Instances viewRL;

	/** The second label view */
	Instances viewSP;

	/** The second probability view */
	Instances viewRP;

	/** --------------- MODEL OF A LINE OF MATRIX-VIEW --------------------- */
	/** CAVWNB model built on the base view */
	public CAVWNB classifier_view1 = new weka.classifiers.bayes.PMWNB.CAVWNB.CAVWNB();

	/** CAVWNB model built on the first label view */
	public Classifier classifierView_SL = new weka.classifiers.bayes.PMWNB.CAVWNB.CAVWNB();

	/** CAVWNB model built on the second label view */
	public Classifier classifierView_RL = new weka.classifiers.bayes.PMWNB.CAVWNB.CAVWNB();

	/** CAVWNB model built on the first probability view */
	public Classifier classifierView_SP = new weka.classifiers.bayes.PMWNB.CAVWNB.CAVWNB();

	/** CAVWNB model built on the second probability view */
	public Classifier classifierView_RP = new weka.classifiers.bayes.PMWNB.CAVWNB.CAVWNB();

	Filter m_Discretize_SP;

	Filter m_Discretize_RP;

	private int numAttrs;

	private int numClasses;

	/** The perturbation strategy to generate the base view */
	private boolean isSupervised;
	private boolean isEFD;
	private int numBins;
	private double m_width;

	public void setFilterIsSupervised(boolean isSuperviesd) {

		this.isSupervised = isSuperviesd;
		if (isSuperviesd) {
			m_Discretize_SP = new weka.filters.supervised.attribute.Discretize();
			m_Discretize_RP = new weka.filters.supervised.attribute.Discretize();
			if (m_Discretize_SP instanceof weka.filters.supervised.attribute.Discretize) {
				((weka.filters.supervised.attribute.Discretize) m_Discretize_SP).setUseBinNumbers(true);
			}
			if (m_Discretize_RP instanceof weka.filters.supervised.attribute.Discretize) {
				((weka.filters.supervised.attribute.Discretize) m_Discretize_SP).setUseBinNumbers(true);
			}
		}
	}

	public void setFilterIsEFD(boolean isEFD) {
		this.isEFD = isEFD;
		if (isEFD) {
			m_Discretize_SP = new weka.filters.unsupervised.attribute.PKIDiscretize();
			m_Discretize_RP = new weka.filters.unsupervised.attribute.PKIDiscretize();
			if (m_Discretize_SP instanceof weka.filters.unsupervised.attribute.PKIDiscretize) {
				((weka.filters.unsupervised.attribute.Discretize) m_Discretize_SP).setUseBinNumbers(true);
			}
			if (m_Discretize_RP instanceof weka.filters.unsupervised.attribute.PKIDiscretize) {
				((weka.filters.unsupervised.attribute.Discretize) m_Discretize_RP).setUseBinNumbers(true);
			}
		}
	}

	/**
	 * Base classifiers Training: ensemble SPODEs on the base view
	 * Latent views construction: the first label and probability view
	 * 
	 * @param data the base view
	 * @throws Exception
	 */
	public void buildClassifier_SPODE(Instances data) throws Exception {
		if (isSupervised && isEFD) {
			throw new Exception("isSupervised & isEFD");
		}
		if (isSupervised || isEFD) {

			for (int i = 0; i < numClasses * numAttrs; i++) {
				Attribute att = new Attribute("attr_num" + i);
				viewSP.insertAttributeAt(att, i);
			}
			for (int i = 0; i < data.numInstances(); i++) {
				String[] view2_attributeValue = new String[numAttrs];
				double[][] view2_attributeValue_p = new double[numAttrs][numClasses];

				/** ------------- Base Classifiers : Classifiy Instances -------------- */
				baseClassifier_S.distributionForInstance_c_p(data.instance(i), view2_attributeValue,
						view2_attributeValue_p);

				/** --------------- Construction of the first label view -------------- */
				for (int j = 0; j < numAttrs; j++) {
					viewSL.instance(i).setValue(j, view2_attributeValue[j]);
				}

				/** ----------- - Construction of the first probability view ---------- */
				for (int j = 0; j < numAttrs; j++) {
					for (int k = 0; k < numClasses; k++)
						viewSP.instance(i).setValue(j * numClasses + k, view2_attributeValue_p[j][k]);
				}
			}

			m_Discretize_SP.setInputFormat(viewSP);
			viewSP = Filter.useFilter(viewSP, m_Discretize_SP);

		} else {
			FastVector listd = new FastVector(numBins);
			for (int j = 0; j < numBins; j++) {
				listd.addElement(String.valueOf(j));
			}

			for (int i = 0; i < numClasses * numAttrs; i++) {
				Attribute att = new Attribute("attr_num" + i, listd);
				viewSP.insertAttributeAt(att, i);
			}
			for (int i = 0; i < data.numInstances(); i++) {
				String[] view2_attributeValue = new String[numAttrs];
				double[][] view2_attributeValue_p = new double[numAttrs][numClasses];

				/** ------------- Base Classifiers : Classifiy Instances -------------- */
				baseClassifier_S.distributionForInstance_c_p(data.instance(i), view2_attributeValue,
						view2_attributeValue_p);

				/** --------------- Construction of the first label view -------------- */
				for (int j = 0; j < numAttrs; j++) {
					viewSL.instance(i).setValue(j, view2_attributeValue[j]);
				}

				/** ----------- - Construction of the first probability view ---------- */
				for (int j = 0; j < numAttrs; j++) {
					for (int k = 0; k < numClasses; k++) {
						double p2 = view2_attributeValue_p[j][k];
						int pp2 = (int) (p2 / m_width);
						if (pp2 == numBins)
							pp2--;
						viewSP.instance(i).setValue(j * numClasses + k, pp2);
					}
				}
			}

		}

		/** Build model on the first label view */
		classifierView_SL.buildClassifier(viewSL);

		/** Build model on the first probability view */
		classifierView_SP.buildClassifier(viewSP);

	}

	/**
	 * Base classifiers Training: ensemble RTs on the base view
	 * Latent views construction: the second label and probability view
	 * 
	 * @param data the base view
	 * @throws Exception
	 */
	public void buildClassifier_RT(Instances data) throws Exception {

		if (isSupervised && isEFD) {
			throw new Exception("isSupervised & isEFD");
		}

		if (isSupervised || isEFD) {
			for (int i = 0; i < numClasses * numAttrs; i++) {
				Attribute att = new Attribute("attr_num" + i);
				viewRP.insertAttributeAt(att, i);
			}

			for (int i = 0; i < data.numInstances(); i++) {
				String[] view3_attributeValue = new String[numAttrs];
				double[][] view3_attributeValue_p = new double[numAttrs][numClasses];

				/** ------------- Base Classifiers : Classifiy Instances -------------- */
				baseClassifier_R.distributionForInstance_c_p(data.instance(i), view3_attributeValue,
						view3_attributeValue_p);

				/** --------------- Construction of the second label view -------------- */
				for (int j = 0; j < numAttrs; j++) {
					viewRL.instance(i).setValue(j, view3_attributeValue[j]);
				}

				/** ----------- - Construction of the second probability view ---------- */
				for (int j = 0; j < numAttrs; j++) {
					for (int k = 0; k < numClasses; k++)
						viewRP.instance(i).setValue(j * numClasses + k, view3_attributeValue_p[j][k]);
				}
			}

			m_Discretize_RP.setInputFormat(viewRP);
			viewRP = Filter.useFilter(viewRP, m_Discretize_RP);
		} else {
			FastVector listd = new FastVector(numBins);
			for (int j = 0; j < numBins; j++) {
				listd.addElement(String.valueOf(j));
			}

			for (int i = 0; i < numClasses * numAttrs; i++) {
				Attribute att = new Attribute("attr_num" + i, listd);
				viewRP.insertAttributeAt(att, i);
			}

			for (int i = 0; i < data.numInstances(); i++) {
				String[] view3_attributeValue = new String[numAttrs];
				double[][] view3_attributeValue_p = new double[numAttrs][numClasses];

				/** ------------- Base Classifiers : Classifiy Instances -------------- */
				baseClassifier_R.distributionForInstance_c_p(data.instance(i), view3_attributeValue,
						view3_attributeValue_p);

				/** --------------- Construction of the second label view -------------- */
				for (int j = 0; j < numAttrs; j++) {
					viewRL.instance(i).setValue(j, view3_attributeValue[j]);
				}

				/** ----------- - Construction of the second probability view ---------- */
				for (int j = 0; j < numAttrs; j++) {
					for (int k = 0; k < numClasses; k++) {
						double p3 = view3_attributeValue_p[j][k];
						int pp3 = (int) (p3 / m_width);
						if (pp3 == numBins)
							pp3--;
						viewRP.instance(i).setValue(j * numClasses + k, pp3);
					}
				}
			}
		}

		/** Build model on the second label view */
		classifierView_RL.buildClassifier(viewRL);

		/** Build model on the second probability view */
		classifierView_RP.buildClassifier(viewRP);
	}

	public void buildClassifier(Instances data) throws Exception {
		numBins = 10;
		m_width = 1.0 / numBins;
		numAttrs = data.numAttributes() - 1;
		numClasses = data.numClasses();

		classifier_view1.buildClassifier(data);

		viewSL = new Instances(data);
		viewRL = new Instances(data);
		viewSP = new Instances(data);
		viewRP = new Instances(data);

		for (int i = 0; i < numAttrs; i++) {
			viewSL.deleteAttributeAt(0);
			viewRL.deleteAttributeAt(0);
			viewSP.deleteAttributeAt(0);
			viewRP.deleteAttributeAt(0);
		}
		FastVector list = new FastVector(data.numClasses());
		for (int j = 0; j < data.numClasses(); j++) {
			list.addElement(String.valueOf(j));
		}

		for (int i = 0; i < numAttrs; i++) {
			Attribute att = new Attribute("attr_num" + i, list);
			viewSL.insertAttributeAt(att, i);
			viewRL.insertAttributeAt(att, i);
		}

		baseClassifier_S.buildClassifier(data);
		baseClassifier_R.buildClassifier(data);

		buildClassifier_SPODE(data);

		buildClassifier_RT(data);
	}

	/**
	 * 
	 * @param instance
	 * @param isSupervised the probability view will be discreted align with
	 *                     the perturbation strategy of base view construction
	 * @return
	 * @throws Exception
	 */
	public double[][] distributionForInstance_RT(Instance instance, boolean isSupervised) throws Exception {
		if (isSupervised && isEFD) {
			throw new Exception("isSupervised & isEFD");
		}

		double[][] result = new double[2][];

		Instances predData_view3 = new Instances(viewRL);
		Instances predData_view3_p = new Instances(viewRP);

		String[] view3_attributeValue = new String[numAttrs];
		double[][] view3_attributeValue_p = new double[numAttrs][numClasses];

		/** ------------- Base classifiers： classify Instance --------------- */
		baseClassifier_R.distributionForInstance_c_p(instance, view3_attributeValue, view3_attributeValue_p);

		/** -------------------- The first label view ------------------------ */

		for (int j = 0; j < numAttrs; j++) {
			predData_view3.instance(0).setValue(j, view3_attributeValue[j]);
		}
		result[0] = classifierView_RL.distributionForInstance(predData_view3.instance(0));

		/** -------------------- The first probability view ------------------- */
		if (isSupervised || isEFD) {
			for (int j = 0; j < numAttrs; j++) {
				for (int k = 0; k < numClasses; k++) {
					predData_view3_p.instance(0).setValue(j * numClasses + k, view3_attributeValue_p[j][k]);
				}
			}
			m_Discretize_RP.input(predData_view3_p.instance(0));
			Instance pp3 = m_Discretize_RP.output();

			result[1] = classifierView_RP.distributionForInstance(pp3);

		} else {
			for (int j = 0; j < numAttrs; j++) {
				for (int k = 0; k < numClasses; k++) {
					double p3 = view3_attributeValue_p[j][k];
					int pp3 = (int) (p3 / m_width);
					if (pp3 == numBins)
						pp3--;
					predData_view3_p.instance(0).setValue(j * numClasses + k, pp3);
				}
			}
			result[1] = classifierView_RP.distributionForInstance(predData_view3_p.instance(0));
		}

		return result;

	}

	/**
	 * 
	 * @param instance
	 * @param isSupervised the probability view will be discreted align with
	 *                     the perturbation strategy of base view construction
	 * @return
	 * @throws Exception
	 */
	public double[][] distributionForInstance_SPODE(Instance instance, boolean isSupervised) throws Exception {
		if (isSupervised && isEFD) {
			throw new Exception("isSupervised & isEFD");
		}
		double[][] result = new double[2][];

		Instances predData_view2 = new Instances(viewSL);
		Instances predData_view2_p = new Instances(viewSP);

		String[] view2_attributeValue = new String[numAttrs];
		double[][] view2_attributeValue_p = new double[numAttrs][numClasses];

		/** ------------- Base classifiers： classify Instance --------------- */
		baseClassifier_S.distributionForInstance_c_p(instance, view2_attributeValue, view2_attributeValue_p);

		/** -------------------- The first label view ------------------------ */
		for (int j = 0; j < numAttrs; j++) {
			predData_view2.instance(0).setValue(j, view2_attributeValue[j]);
		}
		result[0] = classifierView_SL.distributionForInstance(predData_view2.instance(0));

		/** -------------------- The first probability view ------------------- */
		if (isSupervised || isEFD) {
			for (int j = 0; j < numAttrs; j++) {
				for (int k = 0; k < numClasses; k++) {
					predData_view2_p.instance(0).setValue(j * numClasses + k, view2_attributeValue_p[j][k]);
				}
			}
			m_Discretize_SP.input(predData_view2_p.instance(0));
			Instance pp2 = m_Discretize_SP.output();

			result[1] = classifierView_SP.distributionForInstance(pp2);

		} else {
			for (int j = 0; j < numAttrs; j++) {
				for (int k = 0; k < numClasses; k++) {
					double p2 = view2_attributeValue_p[j][k];
					int pp2 = (int) (p2 / m_width);
					if (pp2 == numBins)
						pp2--;
					predData_view2_p.instance(0).setValue(j * numClasses + k, pp2);
				}
			}
			result[1] = classifierView_SP.distributionForInstance(predData_view2_p.instance(0));
		}

		return result;
	}

	/**
	 * @param instance
	 * @return Summation of the class-membership probabilities from models in the
	 *         line of matrix-view
	 * @throws Exception
	 */
	public double[] distributionForInstance5(Instance instance) throws Exception {
		double[][] result = new double[5][];
		/** the class-membership probabilities from models in the base view */
		result[0] = classifier_view1.distributionForInstance(instance);

		/**
		 * the class-membership probabilities from models in the first label and
		 * probability view
		 */
		double[][] temp = distributionForInstance_SPODE(instance, isSupervised);
		result[1] = temp[0];
		result[2] = temp[1];

		/**
		 * the class-membership probabilities from models in the second label and
		 * probability view
		 */
		temp = distributionForInstance_RT(instance, isSupervised);
		result[3] = temp[0];
		result[4] = temp[1];

		/**
		 * Summation of the class-membership probabilities from models in the line of
		 * matrix-view
		 */
		for (int i = 1; i < 5; i++) {
			for (int c = 0; c < numClasses; c++) {
				result[0][c] += result[i][c];
			}
		}
		// Utils.normalize(result[0]);
		return result[0];
	}

	public static void main(String[] args) {
		runClassifier(new PMWNB_L(), args);
	}

}
