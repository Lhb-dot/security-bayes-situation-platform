package weka.classifiers.mkx.DIWNB;

import weka.classifiers.AbstractClassifier;
import weka.classifiers.Classifier;
import weka.classifiers.Evaluation;
import weka.core.Attribute;
import weka.core.Instance;
import weka.core.Instances;
import weka.core.Utils;


public class DIWNB_HL extends AbstractClassifier {

	/**
	 *  Dual-View Instance Weighted NB with Soft Label.
	 *  Submitted to Pattern Recognition
	 */
	
	private static final long serialVersionUID = 1L;

	public KNNs_soft baseClassifier_view2 = new KNNs_soft();

	public Classifier classifier_view1 = new weka.classifiers.mkx.DIWNB.DWNB();

	public Classifier classifier_view2 = new weka.classifiers.mkx.DIWNB.DWNB();
	
	Instances trainData_view2;

	private int numAttr;
	
	private double[] view_weight;
	
	/**
	 * Generates the classifier.
	 *
	 * @param instances 
	 *            set of instances serving as training data
	 * @exception Exception
	 *            if the classifier has not been generated successfully
	 */
	public void buildClassifier(Instances data) throws Exception {

	    //remove instances with missing class
	    Instances instances = new Instances(data);
	    instances.deleteWithMissingClass();
	    
	    //Can classifier handle the data?
	    getCapabilities().testWithFail(instances);
	         
		numAttr = instances.numAttributes() - 1;
		view_weight=new double[2];

		/*
		 * View 1 -- Original Attribute Space
		 */
		
		classifier_view1.buildClassifier(instances);
		
		//calculate original view weight
		Evaluation eval1 = new Evaluation(instances);
		eval1.evaluateModel(classifier_view1, instances);
		view_weight[0] = eval1.pctIncorrect();
		
		/*
		 * -- Generated Attribute Space --
		 */

		//Construct Generated View
		//delete attribute
		trainData_view2 = new Instances(instances);
		for (int i = 0; i < numAttr; i++) {
			trainData_view2.deleteAttributeAt(0);
		} 
		
		//add attribute value      
		for (int i = 0; i < instances.numClasses(); i++) {
			Attribute att = new Attribute("attr_num" + i);
			trainData_view2.insertAttributeAt(att, i);
		}
		baseClassifier_view2.buildClassifier(instances);
		
		for (int i = 0; i < instances.numInstances(); i++) {
			double[] view2_attributeValue = baseClassifier_view2.distributionForInstance(instances.instance(i));
			for (int j = 0; j < instances.numClasses(); j++) {
				trainData_view2.instance(i).setValue(j, view2_attributeValue[j]);
			}
		}
		
		classifier_view2.buildClassifier(trainData_view2);
		
		//calculate generated view weight
		Evaluation eval2 = new Evaluation(trainData_view2);
		eval2.evaluateModel(classifier_view2, trainData_view2);
		view_weight[1] = eval2.pctIncorrect();
		
		//avoid incorrect 0
		if(view_weight[0] == 0.0||view_weight[1] == 0.0) {
			for(int j = 0; j < view_weight.length; j++) {
				view_weight[j] = view_weight[j] + 1.0/instances.numInstances();
			}
		}
					
		Utils.normalize(view_weight);
		
	}
	
	/**
	 * Calculates the class membership probabilities for the given test instance
	 *
	 * @param instance
	 *            the instance to be classified
	 * @return predicted class probability distribution
	 */
	public double[] distributionForInstance(Instance instance) throws Exception {
		
		/*
		 *  -- Original Attribute Space --
		 */
		double[] class_member_prob_m1 = classifier_view1.distributionForInstance(instance);
		
		/*
		 *  -- Generated Attribute Space --
		 */
		Instances predData_view2 = new Instances(trainData_view2);
		double [] view2_attributeValue = baseClassifier_view2.distributionForInstance(instance);
		for (int j = 0; j < instance.numClasses(); j++) {
			predData_view2.instance(0).setValue(j, view2_attributeValue[j]);
		}
		double[] class_member_prob_m2 = classifier_view2.distributionForInstance(predData_view2.instance(0));
		
		/*
		 * Classification
		 */
		double[] prob_WIWNB = new double[predData_view2.numClasses()];
		for (int i = 0; i < predData_view2.numClasses(); i++) {
			prob_WIWNB[i] = class_member_prob_m1[i] * view_weight[1] + class_member_prob_m2[i] * view_weight[0];
		}

		Utils.normalize(prob_WIWNB);
		return prob_WIWNB;
	}

	public static void main(String[] args) {
		runClassifier(new  DIWNB_HL(), args);
	}

}

