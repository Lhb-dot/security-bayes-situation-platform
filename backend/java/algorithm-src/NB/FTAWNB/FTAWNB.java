package weka.classifiers.bayes;

import weka.core.*;
import weka.classifiers.*;

/**
 * Fine tuning attribute weighted naive Bayes (Neurocomputing, 2021)
 * Author: Huan Zhang, Liangxiao Jiang
 */
public class FTAWNB extends AbstractClassifier {

	/** for serialization */
	static final long serialVersionUID = -4503874444306113214L;

	/** The number of class and each attribute value occurs in the dataset */
	private double[][] m_ClassAttCounts;

	/** The number of each class value occurs in the dataset */
	private double[] m_ClassCounts;

	/** The number of values for each attribute in the dataset */
	private int[] m_NumAttValues;

	/** The starting index of each attribute in the dataset */
	private int[] m_StartAttIndex;

	/** The number of values for all attributes in the dataset */
	private int m_TotalAttValues;

	/** The number of classes in the dataset */
	private int m_NumClasses;

	/** The number of attributes including class in the dataset */
	private int m_NumAttributes;

	/** The number of instances in the dataset */
	private int m_NumInstances;

	/** The index of the class attribute in the dataset */
	private int m_ClassIndex;

	/** The number of class and each attribute value occurs in the dataset */
	private double[][] p_aic;

	/** The temp number of class and each attribute value occurs in the dataset */
	private double[][] p_aictmp;

	/** The number of each class value occurs in the dataset */
	private double[] pc;

	/** The number of each attribute value occurs in the dataset */
	private double[] m_AttCounts;

	/** The number of two attributes values occurs in the dataset */
	private double[][] m_AttAttCounts;

	/** The number of class and two attributes values occurs in the dataset */
	private double[][][] m_ClassAttAttCounts;

	/** The 2D array of the mutual information of each pair attributes */
	private double[][] m_mutualInformation;

	/** The learned attribute weight vector */
	private double[] attWeight;

	/**
	 * Generates the classifier.
	 *
	 * @param instances set of instances serving as training data
	 * @exception Exception if the classifier has not been generated successfully
	 */
	public void buildClassifier(Instances instances) throws Exception {

		// initialize variable
		m_NumClasses = instances.numClasses();
		m_ClassIndex = instances.classIndex();
		m_NumAttributes = instances.numAttributes();
		m_NumInstances = instances.numInstances();

		m_TotalAttValues = 0;

		// allocate space for attribute reference arrays
		m_StartAttIndex = new int[m_NumAttributes];
		m_NumAttValues = new int[m_NumAttributes];

		// set the starting index of each attribute and the number of values for
		// each attribute and the total number of values for all attributes(not
		// including class).
		for (int i = 0; i < m_NumAttributes; i++) {
			if (i != m_ClassIndex) {
				m_StartAttIndex[i] = m_TotalAttValues;
				m_NumAttValues[i] = instances.attribute(i).numValues();
				m_TotalAttValues += m_NumAttValues[i];
			} else {
				m_StartAttIndex[i] = -1;
				m_NumAttValues[i] = m_NumClasses;
			}
		}

		// allocate space for counts and frequencies
		m_ClassCounts = new double[m_NumClasses];
		m_ClassAttCounts = new double[m_NumClasses][m_TotalAttValues];

		// Calculate the counts
		for (int k = 0; k < m_NumInstances; k++) {
			int classVal = (int) instances.instance(k).classValue();
			m_ClassCounts[classVal]++;
			int[] attIndex = new int[m_NumAttributes];
			for (int i = 0; i < m_NumAttributes; i++) {
				if (i == m_ClassIndex) {
					attIndex[i] = -1;
				} else {
					attIndex[i] = m_StartAttIndex[i] + (int) instances.instance(k).value(i);
					m_ClassAttCounts[classVal][attIndex[i]]++;
				}
			}
		}

		// learn attribute weights
		attWeight = new double[instances.numAttributes()];
		attWeight = learnAttrWeight(instances);

		// allocate space for counts and frequencies
		pc = new double[m_NumClasses];
		p_aic = new double[m_NumClasses][m_TotalAttValues];
		p_aictmp = new double[m_NumClasses][m_TotalAttValues];
		for (int i = 0; i < m_NumClasses; i++) {
			pc[i] = (m_ClassCounts[i] + 1.0 / m_NumClasses) / (m_NumInstances + 1.0);
		}
		for (int i = 0; i < m_NumClasses; i++) {
			for (int j = 0; j < m_NumAttributes - 1; j++) {
				int len = instances.attribute(j).numValues();
				for (int k = 0; k < len; k++) {
					p_aic[i][m_StartAttIndex[j] + k] = Math.pow(
							(m_ClassAttCounts[i][m_StartAttIndex[j] + k] + 1.0 / len) / (m_ClassCounts[i] + 1.0),
							attWeight[j]);
					p_aictmp[i][m_StartAttIndex[j] + k] = Math.pow(
							(m_ClassAttCounts[i][m_StartAttIndex[j] + k] + 1.0 / len) / (m_ClassCounts[i] + 1.0),
							attWeight[j]);
				}
			}
		}

		int misclassfiedNum_new = 0;
		int misclassfiedNum_old = 0;

		for (int k = 0; k < m_NumInstances; k++) {
			double[] pro = distributionForInstance(instances.instance(k));
			int predictClass = Utils.maxIndex(pro);
			int actualClass = (int) instances.instance(k).classValue();
			if (predictClass != actualClass) {
				misclassfiedNum_new++;
			}
		}

		do {

			for (int i = 0; i < m_NumClasses; i++) {
				for (int j = 0; j < m_NumAttributes - 1; j++) {
					int len = instances.attribute(j).numValues();
					for (int k = 0; k < len; k++) {
						p_aictmp[i][m_StartAttIndex[j] + k] = p_aic[i][m_StartAttIndex[j] + k];
					}
				}
			}

			misclassfiedNum_old = misclassfiedNum_new;
			misclassfiedNum_new = 0;

			for (int k = 0; k < m_NumInstances; k++) {

				Instance inst = instances.instance(k);
				int actualClass = (int) inst.classValue();

				// Definition of local variables
				double[] probs = new double[m_NumClasses];
				// store instance's att values in an int array
				int[] attIndex = new int[m_NumAttributes];
				for (int att = 0; att < m_NumAttributes; att++) {
					if (att == m_ClassIndex)
						attIndex[att] = -1;
					else
						attIndex[att] = m_StartAttIndex[att] + (int) inst.value(att);
				}
				// calculate probabilities for each possible class value
				for (int classVal = 0; classVal < m_NumClasses; classVal++) {
					probs[classVal] = pc[classVal];
					for (int att = 0; att < m_NumAttributes; att++) {
						if (attIndex[att] == -1)
							continue;
						probs[classVal] *= p_aic[classVal][attIndex[att]];
					}
				}

				Utils.normalize(probs);

				int predictClass = Utils.maxIndex(probs);

				double mmaxvalueActual = -1;
				double mminvaluePredict = 1;

				if (predictClass != actualClass) {
					double learningRate = 0.01;
					double error = probs[predictClass] - probs[actualClass];
					for (int att = 0; att < m_NumAttributes - 1; att++) {
						if (p_aic[actualClass][attIndex[att]] > mmaxvalueActual) {
							mmaxvalueActual = p_aic[actualClass][attIndex[att]];
						}
						if (p_aic[predictClass][attIndex[att]] < mminvaluePredict) {
							mminvaluePredict = p_aic[predictClass][attIndex[att]];
						}
					}
					for (int att = 0; att < m_NumAttributes - 1; att++) {
						p_aic[actualClass][attIndex[att]] += learningRate
								* (2 * mmaxvalueActual - p_aic[actualClass][attIndex[att]]) * error;
						p_aic[predictClass][attIndex[att]] -= learningRate
								* (2 * p_aic[predictClass][attIndex[att]] - mminvaluePredict) * error;

					}
					misclassfiedNum_new++;
				}
			}

			if (misclassfiedNum_new >= misclassfiedNum_old) {
				for (int i = 0; i < m_NumClasses; i++) {
					for (int j = 0; j < m_NumAttributes - 1; j++) {
						int len = instances.attribute(j).numValues();
						for (int k = 0; k < len; k++) {
							p_aic[i][m_StartAttIndex[j] + k] = p_aictmp[i][m_StartAttIndex[j] + k];
						}
					}
				}

				break;

			}

		} while (true);

	}

	/**
	 * Calculates the class membership probabilities for the given test instance
	 *
	 * @param instance the instance to be classified
	 * @return predicted class probability distribution
	 * @exception Exception if there is a problem generating the prediction
	 */
	public double[] distributionForInstance(Instance instance) throws Exception {

		// Definition of local variables
		double[] probs = new double[m_NumClasses];
		// store instance's att values in an int array
		int[] attIndex = new int[m_NumAttributes];
		for (int att = 0; att < m_NumAttributes; att++) {
			if (att == m_ClassIndex)
				attIndex[att] = -1;
			else
				attIndex[att] = m_StartAttIndex[att] + (int) instance.value(att);
		}
		// calculate probabilities for each possible class value
		for (int classVal = 0; classVal < m_NumClasses; classVal++) {
			probs[classVal] = pc[classVal];
			for (int att = 0; att < m_NumAttributes; att++) {
				if (attIndex[att] == -1)
					continue;
				probs[classVal] *= p_aic[classVal][attIndex[att]];
			}
		}

		Utils.normalize(probs);
		return probs;
	}

	/**
	 * Main method for testing this class.
	 *
	 * @param argv the options
	 */
	public static void main(String[] argv) {
		try {
			System.out.println(Evaluation.evaluateModel(new FTAWNB(), argv));
		} catch (Exception e) {
			e.printStackTrace();
			System.err.println(e.getMessage());
		}
	}

	/**
	 * Generates the attribute weights using CFWNB.
	 *
	 * @param instances set of instances serving as training data
	 * @exception Exception if the classifier has not been generated successfully
	 */

	public double[] learnAttrWeight(Instances instances) throws Exception {

		// reset variable
		m_NumClasses = instances.numClasses();
		m_ClassIndex = instances.classIndex();
		m_NumAttributes = instances.numAttributes();
		m_NumInstances = instances.numInstances();
		m_TotalAttValues = 0;

		// allocate space for attribute reference arrays
		m_StartAttIndex = new int[m_NumAttributes];
		m_NumAttValues = new int[m_NumAttributes];

		// set the starting index of each attribute and the number of values for
		// each attribute and the total number of values for all attributes (not
		// including class).
		for (int i = 0; i < m_NumAttributes; i++) {
			m_StartAttIndex[i] = m_TotalAttValues;
			m_NumAttValues[i] = instances.attribute(i).numValues();
			m_TotalAttValues += m_NumAttValues[i];
		}

		// allocate space for counts and frequencies
		m_ClassCounts = new double[m_NumClasses];
		m_AttCounts = new double[m_TotalAttValues];
		m_AttAttCounts = new double[m_TotalAttValues][m_TotalAttValues];
		m_ClassAttAttCounts = new double[m_NumClasses][m_TotalAttValues][m_TotalAttValues];

		// Calculate the counts
		for (int k = 0; k < m_NumInstances; k++) {
			int classVal = (int) instances.instance(k).classValue();
			m_ClassCounts[classVal]++;
			int[] attIndex = new int[m_NumAttributes];
			for (int i = 0; i < m_NumAttributes; i++) {
				attIndex[i] = m_StartAttIndex[i] + (int) instances.instance(k).value(i);
				m_AttCounts[attIndex[i]]++;
			}
			for (int Att1 = 0; Att1 < m_NumAttributes; Att1++) {
				for (int Att2 = 0; Att2 < m_NumAttributes; Att2++) {
					m_AttAttCounts[attIndex[Att1]][attIndex[Att2]]++;
					m_ClassAttAttCounts[classVal][attIndex[Att1]][attIndex[Att2]]++;
				}
			}
		}

		// compute mutual information between each pair attributes (including
		// class)
		m_mutualInformation = new double[m_NumAttributes][m_NumAttributes];
		for (int att1 = 0; att1 < m_NumAttributes; att1++) {
			for (int att2 = att1 + 1; att2 < m_NumAttributes; att2++) {
				m_mutualInformation[att1][att2] = mutualInfo(att1, att2);
				m_mutualInformation[att2][att1] = m_mutualInformation[att1][att2];
			}
		}

		double ave = 0;
		for (int att1 = 0; att1 < m_NumAttributes; att1++) {
			if (att1 == m_ClassIndex)
				continue;
			ave += m_mutualInformation[att1][m_ClassIndex];
		}
		ave /= (m_NumAttributes - 1);
		for (int att1 = 0; att1 < m_NumAttributes; att1++) {
			if (att1 == m_ClassIndex)
				continue;
			m_mutualInformation[att1][m_ClassIndex] /= ave;
		}
		double mean = 0;
		for (int att1 = 0; att1 < m_NumAttributes; att1++) {
			if (att1 == m_ClassIndex)
				continue;
			for (int att2 = 0; att2 < m_NumAttributes; att2++) {
				if (att2 == m_ClassIndex || att2 == att1)
					continue;
				mean += m_mutualInformation[att1][att2];
			}
		}
		mean /= ((m_NumAttributes - 1) * (m_NumAttributes - 2));
		for (int att1 = 0; att1 < m_NumAttributes; att1++) {
			if (att1 == m_ClassIndex)
				continue;
			for (int att2 = 0; att2 < m_NumAttributes; att2++) {
				if (att2 == m_ClassIndex || att2 == att1)
					continue;
				m_mutualInformation[att1][att2] /= mean;
			}
		}

		double[] aveMutualInfo = new double[m_NumAttributes];
		for (int att1 = 0; att1 < m_NumAttributes; att1++) {
			if (att1 == m_ClassIndex)
				continue;
			for (int att2 = 0; att2 < m_NumAttributes; att2++) {
				if (att2 == m_ClassIndex || att2 == att1)
					continue;
				aveMutualInfo[att1] += m_mutualInformation[att1][att2];
			}
			aveMutualInfo[att1] /= (m_NumAttributes - 2);
		}

		double[] m_Weight = new double[m_NumAttributes];
		for (int att1 = 0; att1 < m_NumAttributes; att1++) {
			if (att1 == m_ClassIndex)
				continue;
			m_Weight[att1] = 1 / (1 + Math.exp(-(m_mutualInformation[att1][m_ClassIndex] - aveMutualInfo[att1])));
		}

		return m_Weight;
	}

	/**
	 * compute the mutual information between each pair attributes (including class)
	 *
	 * @param args att1, att2 are two attributes
	 * @return the mutual information between each pair attributes
	 */

	private double mutualInfo(int att1, int att2) throws Exception {

		double mutualInfo = 0;
		int attIndex1 = m_StartAttIndex[att1];
		int attIndex2 = m_StartAttIndex[att2];
		double[] PriorsAtt1 = new double[m_NumAttValues[att1]];
		double[] PriorsAtt2 = new double[m_NumAttValues[att2]];
		double[][] PriorsAtt1Att2 = new double[m_NumAttValues[att1]][m_NumAttValues[att2]];

		for (int i = 0; i < m_NumAttValues[att1]; i++) {
			PriorsAtt1[i] = m_AttCounts[attIndex1 + i] / m_NumInstances;
		}

		for (int j = 0; j < m_NumAttValues[att2]; j++) {
			PriorsAtt2[j] = m_AttCounts[attIndex2 + j] / m_NumInstances;
		}

		for (int i = 0; i < m_NumAttValues[att1]; i++) {
			for (int j = 0; j < m_NumAttValues[att2]; j++) {
				PriorsAtt1Att2[i][j] = m_AttAttCounts[attIndex1 + i][attIndex2 + j] / m_NumInstances;
			}
		}

		for (int i = 0; i < m_NumAttValues[att1]; i++) {
			for (int j = 0; j < m_NumAttValues[att2]; j++) {
				mutualInfo += PriorsAtt1Att2[i][j] * log2(PriorsAtt1Att2[i][j], PriorsAtt1[i] * PriorsAtt2[j]);
			}
		}
		return mutualInfo;
	}

	/**
	 * compute the logarithm whose base is 2.
	 *
	 * @param args x,y are numerator and denominator of the fraction.
	 * @return the natural logarithm of this fraction.
	 */
	private double log2(double x, double y) {

		if (x < 1e-6 || y < 1e-6)
			return 0.0;
		else
			return Math.log(x / y) / Math.log(2);
	}

}
