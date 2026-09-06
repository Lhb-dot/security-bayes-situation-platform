package weka.classifiers.zh.MVCAVWNB;

import weka.classifiers.AbstractClassifier;
import weka.classifiers.Classifier;
import weka.core.Attribute;
import weka.core.FastVector;
import weka.core.Instance;
import weka.core.Instances;
import weka.core.Utils;
import weka.core.converters.ArffSaver;
import weka.filters.Filter;
import weka.filters.unsupervised.attribute.Discretize;

import weka.classifiers.zh.CAVWNB.CAVWNB;

public class MVCAVWNB extends AbstractClassifier {

	public SPODE baseClassifier_view2 = new SPODE();

	public RF_m baseClassifier_view3 = new RF_m();

	public Classifier classifier_view1 = new weka.classifiers.zh.CAVWNB.CAVWNB();

	public Classifier classifier_view2 = new weka.classifiers.zh.CAVWNB.CAVWNB();

	public Classifier classifier_view3 = new weka.classifiers.zh.CAVWNB.CAVWNB();

	Instances trainData_view2;

	Instances trainData_view3;

	private int numAttr;

	public void buildClassifier(Instances data) throws Exception {

		numAttr = data.numAttributes() - 1;

		/*
		 * View 1 -- Original Attribute Space
		 */
		classifier_view1.buildClassifier(data);

		/*
		 * View 2 -- SPODE Attribute Space
		 */

		// Construct View 2 Attribute Space
		trainData_view2 = new Instances(data);
		for (int i = 0; i < numAttr; i++) {
			trainData_view2.deleteAttributeAt(0);
		}
		for (int i = 0; i < numAttr; i++) {
			FastVector list = new FastVector(data.numClasses());
			for (int j = 0; j < data.numClasses(); j++) {
				list.addElement(String.valueOf(j));
			}
			Attribute att = new Attribute("attr_num" + i, list);
			trainData_view2.insertAttributeAt(att, i);
		}

		baseClassifier_view2.buildClassifier(data);
		for (int i = 0; i < data.numInstances(); i++) {
			String[] view2_attributeValue = baseClassifier_view2.distributionForInstance2(data.instance(i));
			for (int j = 0; j < numAttr; j++) {
				trainData_view2.instance(i).setValue(j, view2_attributeValue[j]);
			}
		}

		classifier_view2.buildClassifier(trainData_view2);

		/*
		 * View 3 -- RF Attribute Space
		 */

		// Construct View 3 Attribute Space
		trainData_view3 = new Instances(data);
		for (int i = 0; i < numAttr; i++) {
			trainData_view3.deleteAttributeAt(0);
		}
		for (int i = 0; i < numAttr; i++) {
			FastVector list = new FastVector(data.numClasses());
			for (int j = 0; j < data.numClasses(); j++) {
				list.addElement(String.valueOf(j));
			}
			Attribute att = new Attribute("attr_num" + i, list);
			trainData_view3.insertAttributeAt(att, i);
		}

		baseClassifier_view3.buildClassifier(data);
		for (int i = 0; i < data.numInstances(); i++) {
			String[] view3_attributeValue = baseClassifier_view3.distributionForInstance1(data.instance(i));
			for (int j = 0; j < numAttr; j++) {
				trainData_view3.instance(i).setValue(j, view3_attributeValue[j]);
			}
		}

		classifier_view3.buildClassifier(trainData_view3);

	}

	public double[] distributionForInstance(Instance instance) throws Exception {

		/*
		 * View 1 -- Original Attribute Space
		 */
		double[] class_member_prob_m1 = classifier_view1.distributionForInstance(instance);

		/*
		 * View 2 -- SPODE Attribute Space
		 */
		Instances predData_view2 = new Instances(trainData_view2);
		String[] view2_attributeValue = baseClassifier_view2.distributionForInstance2(instance);
		for (int j = 0; j < numAttr; j++) {
			predData_view2.instance(0).setValue(j, view2_attributeValue[j]);
		}
		double[] class_member_prob_m2 = classifier_view2.distributionForInstance(predData_view2.instance(0));

		/*
		 * View 3 -- RF Attribute Space
		 */
		Instances predData_view3 = new Instances(trainData_view3);
		String[] view3_attributeValue = baseClassifier_view3.distributionForInstance1(instance);
		for (int j = 0; j < numAttr; j++) {
			predData_view3.instance(0).setValue(j, view3_attributeValue[j]);
		}
		double[] class_member_prob_m3 = classifier_view3.distributionForInstance(predData_view3.instance(0));

		/*
		 * Classification
		 */
		double[] prob_MVCAVWNB = new double[predData_view3.numClasses()];
		for (int i = 0; i < predData_view3.numClasses(); i++) {
			prob_MVCAVWNB[i] = class_member_prob_m1[i] + class_member_prob_m2[i] + class_member_prob_m3[i];
		}

		Utils.normalize(prob_MVCAVWNB);
		return prob_MVCAVWNB;
	}

	public double[] distributionForInstance5(Instance instance) throws Exception {

		/*
		 * View 1 -- Original Attribute Space
		 */
		double[] class_member_prob_m1 = classifier_view1.distributionForInstance(instance);

		/*
		 * View 2 -- SPODE Attribute Space
		 */
		Instances predData_view2 = new Instances(trainData_view2);
		String[] view2_attributeValue = baseClassifier_view2.distributionForInstance2(instance);
		for (int j = 0; j < numAttr; j++) {
			predData_view2.instance(0).setValue(j, view2_attributeValue[j]);
		}
		double[] class_member_prob_m2 = classifier_view2.distributionForInstance(predData_view2.instance(0));

		/*
		 * View 3 -- RF Attribute Space
		 */
		Instances predData_view3 = new Instances(trainData_view3);
		String[] view3_attributeValue = baseClassifier_view3.distributionForInstance1(instance);
		for (int j = 0; j < numAttr; j++) {
			predData_view3.instance(0).setValue(j, view3_attributeValue[j]);
		}
		double[] class_member_prob_m3 = classifier_view3.distributionForInstance(predData_view3.instance(0));

		/*
		 * Classification
		 */
		double[] prob_MVCAVWNB = new double[predData_view3.numClasses()];
		for (int i = 0; i < predData_view3.numClasses(); i++) {
			prob_MVCAVWNB[i] = class_member_prob_m1[i] + class_member_prob_m2[i] + class_member_prob_m3[i];
		}

		// Utils.normalize(prob_MVCAVWNB);
		return prob_MVCAVWNB;
	}

	public double[] distributionForInstance_SPODE_Label(Instance instance) throws Exception {

		/*
		 * View 2 -- SPODE Attribute Space
		 */
		Instances predData_view2 = new Instances(trainData_view2);
		String[] view2_attributeValue = baseClassifier_view2.distributionForInstance2(instance);
		for (int j = 0; j < numAttr; j++) {
			predData_view2.instance(0).setValue(j, view2_attributeValue[j]);
		}
		double[] class_member_prob_m2 = classifier_view2.distributionForInstance(predData_view2.instance(0));

		return class_member_prob_m2;
	}

	public double[] distributionForInstance_RT_Label(Instance instance) throws Exception {

		/*
		 * View 3 -- RF Attribute Space
		 */
		Instances predData_view3 = new Instances(trainData_view3);
		String[] view3_attributeValue = baseClassifier_view3.distributionForInstance1(instance);
		for (int j = 0; j < numAttr; j++) {
			predData_view3.instance(0).setValue(j, view3_attributeValue[j]);
		}
		double[] class_member_prob_m3 = classifier_view3.distributionForInstance(predData_view3.instance(0));

		return class_member_prob_m3;
	}

	/**
	 * Per-view binary log-odds evidence (same preprocessing as
	 * {@link #distributionForInstance(Instance)}). {@code result[v][u]} matches
	 * {@link CAVWNB#evidenceWeightForBinaryClassification(Instance)}; last index
	 * of each row is {@code log P(c0)-log P(c1)} for that view. Requires two
	 * classes and {@link CAVWNB} as each view classifier.
	 */
	public double[][] evidenceWeightForBinaryClassification_allViews(Instance instance) throws Exception {

		double[][] ans = new double[3][];

		ans[0] = ((CAVWNB) classifier_view1).evidenceWeightForBinaryClassification(instance);

		Instances predData_view2 = new Instances(trainData_view2);
		String[] view2_attributeValue = baseClassifier_view2.distributionForInstance2(instance);
		for (int j = 0; j < numAttr; j++) {
			predData_view2.instance(0).setValue(j, view2_attributeValue[j]);
		}
		ans[1] = ((CAVWNB) classifier_view2).evidenceWeightForBinaryClassification(predData_view2.instance(0));

		Instances predData_view3 = new Instances(trainData_view3);
		String[] view3_attributeValue = baseClassifier_view3.distributionForInstance1(instance);
		for (int j = 0; j < numAttr; j++) {
			predData_view3.instance(0).setValue(j, view3_attributeValue[j]);
		}
		ans[2] = ((CAVWNB) classifier_view3).evidenceWeightForBinaryClassification(predData_view3.instance(0));

		return ans;
	}

	public static void main(String[] args) {
		runClassifier(new MVCAVWNB(), args);
	}

}
