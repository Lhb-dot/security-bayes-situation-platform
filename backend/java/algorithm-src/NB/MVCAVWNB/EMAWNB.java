package weka.classifiers.zh.MVCAVWNB;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.Random;

import org.netlib.util.intW;

import weka.classifiers.AbstractClassifier;
import weka.classifiers.Classifier;
import weka.core.Attribute;
import weka.core.Instance;
import weka.core.Instances;
import weka.core.Utils;
import weka.filters.Filter;
import weka.filters.unsupervised.attribute.Discretize;

public class EMAWNB extends AbstractClassifier {

	private Instances m_Instances;
	private int numInstances;
	private int numAtts;
	private int numClasses;

	private Instances training_ins;
	private Instances test_ins;

	private int numFolds;
	private int k;

	private double[] dis;
	private int[] ins_k;
	private double max_dis;

	public SPODE[] baseClassifier_view2;

	public RF_m[] baseClassifier_view3;

	Instances trainData_view2;

	Instances trainData_view3;

	public double w_view1;
	public double w_view2;
	public double w_view3;

	public Classifier classifier_view1 = new weka.classifiers.zh.CAVWNB.CAVWNB();

	public Classifier classifier_view2 = new weka.classifiers.zh.CAVWNB.CAVWNB();

	public Classifier classifier_view3 = new weka.classifiers.zh.CAVWNB.CAVWNB();

	@Override
	public void buildClassifier(Instances data) throws Exception {

		m_Instances = new Instances(data);
		numClasses = data.numClasses();
		numAtts = data.numAttributes() - 1;
		numInstances = data.numInstances();

		numFolds = 10;
		k = 30;

		if (m_Instances.classAttribute().isNominal()) {
			m_Instances.stratify(numFolds);
		}
		ArrayList list = new ArrayList<String>(m_Instances.numClasses());
		for (int j = 0; j < m_Instances.numClasses(); j++) {
			list.add(String.valueOf(j));
		}

		baseClassifier_view2 = new SPODE[numFolds];
		baseClassifier_view3 = new RF_m[numFolds];
		for (int i = 0; i < numFolds; i++) {
			baseClassifier_view2[i] = new SPODE();
			baseClassifier_view3[i] = new RF_m();
		}

		trainData_view2 = new Instances(m_Instances);
		trainData_view3 = new Instances(m_Instances);
		for (int i = 0; i < numAtts; i++) {
			trainData_view2.deleteAttributeAt(0);
			trainData_view3.deleteAttributeAt(0);
		}
		for (int i = 0; i < numAtts; i++) {
			Attribute att = new Attribute("attr_num" + i, list);
			trainData_view2.insertAttributeAt(att, i);
			trainData_view3.insertAttributeAt(att, i);
		}

		for (int i = 0; i < numFolds; i++) {
			training_ins = m_Instances.trainCV(numFolds, i);
			test_ins = m_Instances.testCV(numFolds, i);
			baseClassifier_view2[i].buildClassifier(training_ins);
			baseClassifier_view3[i].buildClassifier(training_ins);
			int numInstForFold = numInstances / numFolds;
			int offset;
			if (i < numInstances % numFolds) {
				numInstForFold++;
				offset = i;
			} else {
				offset = numInstances % numFolds;
			}

			int first = i * (numInstances / numFolds) + offset;

			for (int k = 0; k < numInstForFold; k++) {
				int ins_ind = first + k;
				if (ins_ind >= numInstances)
					break;
				String[] view2_attVal = baseClassifier_view2[i].distributionForInstance2(test_ins.instance(k));
				String[] view3_attVal = baseClassifier_view3[i].distributionForInstance1(test_ins.instance(k));
				for (int view_ins_att = 0; view_ins_att < numAtts; view_ins_att++) {
					trainData_view2.instance(ins_ind).setValue(view_ins_att, view2_attVal[view_ins_att]);
					trainData_view3.instance(ins_ind).setValue(view_ins_att, view3_attVal[view_ins_att]);
				}
			}
		}
		classifier_view1.buildClassifier(m_Instances);
		classifier_view2.buildClassifier(trainData_view2);
		classifier_view3.buildClassifier(trainData_view3);
	}

	@Override
	public double[] distributionForInstance(Instance instance) throws Exception {

		double probs[] = new double[numClasses];

		LearningViewWweight(instance);

		double[] probs1 = distributionForInstance1(instance);
		double[] probs2 = distributionForInstance2(instance);
		double[] probs3 = distributionForInstance3(instance);

		for (int i = 0; i < numClasses; i++) {
			if (w_view1 + w_view2 + w_view3 == 0) {
				probs[i] = probs1[i] + probs2[i] + probs3[i];
			} else
				probs[i] = probs1[i] * w_view1 + probs2[i] * w_view2 + probs3[i] * w_view3;
		}

		Utils.normalize(probs);
		return probs;
	}

	public double[] distributionForInstance1(Instance instance) throws Exception {
	
		double[] probs = classifier_view1.distributionForInstance(instance);
		return probs;
	}

	public void LearningViewWweight(Instance instance) throws Exception {
		w_view1 = w_view2 = w_view3 = 0;
		getDistance(instance);
		ins_k = Utils.sort(dis);
		max_dis = dis[(int) ins_k[k - 1]];
		double[] weight = new double[numInstances];
		for (int i = 0; i < numInstances; i++) {
			if (max_dis != 0)
				weight[i] = 1 - dis[i] / max_dis;
			else
				weight[i] = 1 - dis[i];
		}
		int cnt = 0;
		for (int i = 0; i < k; i++) {
			int ins_id = ins_k[i];
			int class_id = (int) m_Instances.instance(ins_id).classValue();
			double[] probs1 = distributionForInstance1(m_Instances.instance(ins_id));
			double[] probs2 = distributionForInstance2(m_Instances.instance(ins_id));
			double[] probs3 = distributionForInstance3(m_Instances.instance(ins_id));
			double w = weight[ins_id];
			w_view1 += probs1[class_id] * w;
			w_view2 += probs2[class_id] * w;
			w_view3 += probs3[class_id] * w;
		}

	}

	public double[] distributionForInstance2(Instance instance) throws Exception {
	
		/*
		 * View 2 -- SPODE Attribute Space
		 */
		Instances predData_view2 = new Instances(trainData_view2);
		double[] probs_pred = new double[numClasses * numAtts];
		for (int i = 0; i < numFolds; i++) {
			double[] temp = baseClassifier_view2[i].distributionForInstance3(instance);
			for (int j = 0; j < numAtts * numClasses; j++) {
				probs_pred[j] += temp[j];
			}
		}
		double[][] each_probs = new double[numAtts][numClasses];
		for (int i = 0; i < numAtts; i++)
			for (int j = 0; j < numClasses; j++)
				each_probs[i][j] = probs_pred[i * numClasses + j];

		String[] aa = new String[numAtts];
		for (int i = 0; i < numAtts; i++)
			aa[i] = String.valueOf(Utils.maxIndex(each_probs[i]));

		for (int j = 0; j < numAtts; j++) {
			predData_view2.instance(0).setValue(j, aa[j]);
		}
		double[] probs = classifier_view2.distributionForInstance(predData_view2.instance(0));
		return probs;
	}

	public double[] distributionForInstance3(Instance instance) throws Exception {
	
		Instances predData_view3 = new Instances(trainData_view3);
		double[] probs_pred = new double[numClasses * numAtts];
		for (int i = 0; i < numFolds; i++) {
			double[] temp = baseClassifier_view3[i].distributionForInstance2(instance);
			for (int j = 0; j < numAtts * numClasses; j++) {
				probs_pred[j] += temp[j];
			}
		}
		double[][] each_probs = new double[numAtts][numClasses];
		for (int i = 0; i < numAtts; i++)
			for (int j = 0; j < numClasses; j++)
				each_probs[i][j] = probs_pred[i * numClasses + j];

		String[] aa = new String[numAtts];
		for (int i = 0; i < numAtts; i++)
			aa[i] = String.valueOf(Utils.maxIndex(each_probs[i]));

		for (int j = 0; j < numAtts; j++) {
			predData_view3.instance(0).setValue(j, aa[j]);
		}
		double[] probs = classifier_view3.distributionForInstance(predData_view3.instance(0));
		return probs;
	}

	public void getDistance(Instance instance) {
		dis = new double[numInstances];
		for (int i = 0; i < numInstances; i++) {
			dis[i] = 0;
			for (int j = 0; j < numAtts; j++) {
				if (instance.value(j) != m_Instances.instance(i).value(j))
					dis[i]++;
			}
		}
	}

	public static void main(String[] args) {
		runClassifier(new EMAWNB(), args);
	}
}