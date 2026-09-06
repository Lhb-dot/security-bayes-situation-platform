package weka.classifiers.bayes.PMWNB.PMWNB;

import java.util.*;
import weka.core.*;
import weka.classifiers.*;

public class SPODE extends AbstractClassifier {

	/** The number of each class value occurs in the dataset */
	private double[] m_ClassCounts;

	/** The number of each attribute value occurs in the dataset */
	private double[] m_AttCounts;

	/** The number of two attributes values occurs in the dataset */
	private double[][] m_AttAttCounts;

	/** The number of class and two attributes values occurs in the dataset */
	private double[][][] m_ClassAttAttCounts;

	/** The number of values for each attribute in the dataset */
	private int[] m_NumAttValues;

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

	/** The starting index of each attribute in the dataset */
	private int[] m_StartAttIndex;

	/** An att's frequency must be this value or more to be a root of tree */
	private int m_NumRoot = 0;

	/**
	 * Generates the classifier.
	 *
	 * @param instances set of instances serving as training data
	 * @exception Exception if the classifier has not been generated successfully
	 */
	public void buildClassifier(Instances instances) throws Exception {

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
		m_AttCounts = new double[m_TotalAttValues];
		m_AttAttCounts = new double[m_TotalAttValues][m_TotalAttValues];
		m_ClassAttAttCounts = new double[m_NumClasses][m_TotalAttValues][m_TotalAttValues];

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
					m_AttCounts[attIndex[i]]++;
				}
			}
			for (int Att1 = 0; Att1 < m_NumAttributes; Att1++) {
				if (attIndex[Att1] == -1)
					continue;
				for (int Att2 = 0; Att2 < m_NumAttributes; Att2++) {
					if ((attIndex[Att2] != -1)) {
						m_AttAttCounts[attIndex[Att1]][attIndex[Att2]] += instances.instance(k).weight();
						m_ClassAttAttCounts[classVal][attIndex[Att1]][attIndex[Att2]] += instances.instance(k).weight();
					}
				}
			}
		}
	}

	public double[] distributionForInstance(Instance instance) throws Exception {

		// Definition of local variables
		double[] probs = new double[m_NumClasses];
		double prob;
		int numRoot;

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
			probs[classVal] = 0;
			numRoot = 0;
			for (int parent = 0; parent < m_NumAttributes; parent++) {
				if (attIndex[parent] == -1 || m_AttCounts[attIndex[parent]] < m_NumRoot)
					continue;
				numRoot++;
				prob = (m_ClassAttAttCounts[classVal][attIndex[parent]][attIndex[parent]] + 1.0)
						/ (m_NumInstances + m_NumClasses * m_NumAttValues[parent]);
				for (int son = 0; son < m_NumAttributes; son++) {
					if (attIndex[son] == -1 || son == parent)
						continue;
					prob *= (m_ClassAttAttCounts[classVal][attIndex[parent]][attIndex[son]] + 1.0)
							/ (m_ClassAttAttCounts[classVal][attIndex[parent]][attIndex[parent]] + m_NumAttValues[son]);
				}
				probs[classVal] += prob;
			}
			if (numRoot >= 1) {
				probs[classVal] /= numRoot;
			} else {
				probs[classVal] = (m_ClassCounts[classVal] + 1.0) / (m_NumInstances + m_NumClasses);
				for (int son = 0; son < m_NumAttributes; son++) {
					if (attIndex[son] == -1)
						continue;
					probs[classVal] *= (m_ClassAttAttCounts[classVal][attIndex[son]][attIndex[son]] + 1.0)
							/ (m_ClassCounts[classVal] + m_NumAttValues[son]);
				}
			}
		}
		Utils.normalize(probs);
		return probs;
	}

	/**
	 * Calculates the class membership probabilities for the given test instance
	 *
	 * @param instance the instance to be classified
	 * @return predicted class probability distribution
	 * @exception Exception if there is a problem generating the prediction
	 */
	public String[] distributionForInstance2(Instance instance) throws Exception {

		// Definition of local variables
		double[] probs = new double[m_NumClasses];
		double prob;
		int numRoot;

		double[][] result = new double[m_NumAttributes - 1][m_NumClasses];

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
			probs[classVal] = 0;
			numRoot = 0;
			for (int parent = 0; parent < m_NumAttributes; parent++) {
				if (attIndex[parent] == -1 || m_AttCounts[attIndex[parent]] < m_NumRoot)
					continue;
				numRoot++;
				prob = (m_ClassAttAttCounts[classVal][attIndex[parent]][attIndex[parent]] + 1.0)
						/ (m_NumInstances + m_NumClasses * m_NumAttValues[parent]);
				for (int son = 0; son < m_NumAttributes; son++) {
					if (attIndex[son] == -1 || son == parent)
						continue;
					prob *= (m_ClassAttAttCounts[classVal][attIndex[parent]][attIndex[son]] + 1.0)
							/ (m_ClassAttAttCounts[classVal][attIndex[parent]][attIndex[parent]] + m_NumAttValues[son]);
				}
				result[parent][classVal] = prob;
				probs[classVal] += prob;
			}
			if (numRoot >= 1) {
				probs[classVal] /= numRoot;
			} else {
				probs[classVal] = (m_ClassCounts[classVal] + 1.0) / (m_NumInstances + m_NumClasses);
				for (int son = 0; son < m_NumAttributes; son++) {
					if (attIndex[son] == -1)
						continue;
					probs[classVal] *= (m_ClassAttAttCounts[classVal][attIndex[son]][attIndex[son]] + 1.0)
							/ (m_ClassCounts[classVal] + m_NumAttValues[son]);
				}
				for (int parent = 0; parent < m_NumAttributes - 1; parent++) {
					result[parent][classVal] = probs[classVal];
				}
			}
		}

		String[] aa = new String[m_NumAttributes - 1];
		for (int i = 0; i < m_NumAttributes - 1; i++) {
			aa[i] = String.valueOf(Utils.maxIndex(result[i]));
		}

		return aa;
	}

	public void distributionForInstance_c_p(Instance instance, String[] pred_label, double[][] pred_probs) {
		// Definition of local variables
		double prob;
		int numRoot;

		double[][] result = new double[m_NumAttributes - 1][m_NumClasses];
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
			probs[classVal] = 0;
			numRoot = 0;
			for (int parent = 0; parent < m_NumAttributes; parent++) {
				if (attIndex[parent] == -1 || m_AttCounts[attIndex[parent]] < m_NumRoot)
					continue;
				numRoot++;
				prob = (m_ClassAttAttCounts[classVal][attIndex[parent]][attIndex[parent]] + 1.0)
						/ (m_NumInstances + m_NumClasses * m_NumAttValues[parent]);

				for (int son = 0; son < m_NumAttributes; son++) {
					if (attIndex[son] == -1 || son == parent)
						continue;

					prob *= (m_ClassAttAttCounts[classVal][attIndex[parent]][attIndex[son]] + 1.0)
							/ (m_ClassAttAttCounts[classVal][attIndex[parent]][attIndex[parent]] + m_NumAttValues[son]);
				}
				result[parent][classVal] = prob;
				probs[classVal] += prob;
			}
			if (numRoot >= 1) {
				probs[classVal] /= numRoot;
			} else {
				probs[classVal] = (m_ClassCounts[classVal] + 1.0) / (m_NumInstances + m_NumClasses);
				for (int son = 0; son < m_NumAttributes; son++) {
					if (attIndex[son] == -1)
						continue;
					probs[classVal] *= (m_ClassAttAttCounts[classVal][attIndex[son]][attIndex[son]] + 1.0)
							/ (m_ClassCounts[classVal] + m_NumAttValues[son]);
				}
				for (int parent = 0; parent < m_NumAttributes - 1; parent++) {
					result[parent][classVal] = probs[classVal];
				}
			}

		}
		for (int i = 0; i < m_NumAttributes - 1; i++) {
			Utils.normalize(result[i]);
		}
		for (int i = 0; i < m_NumAttributes - 1; i++) {
			for (int j = 0; j < m_NumClasses; j++) {
				pred_probs[i][j] = result[i][j];
			}
		}

		for (int i = 0; i < m_NumAttributes - 1; i++) {
			pred_label[i] = String.valueOf(Utils.maxIndex(result[i]));
		}

	}

	/**
	 * Calculates the class membership probabilities for the given test instance
	 *
	 * @param instance the instance to be classified
	 * @return predicted class probability distribution
	 * @exception Exception if there is a problem generating the prediction
	 */
	public double[] distributionForInstance3(Instance instance) throws Exception {

		// Definition of local variables
		double[] probs = new double[m_NumClasses];
		double prob;
		int numRoot;

		double[][] result = new double[m_NumAttributes - 1][m_NumClasses];

		// store instance's att values in an int array
		int[] attIndex = new int[m_NumAttributes];
		for (int att = 0; att < m_NumAttributes; att++) {
			if (att == m_ClassIndex)
				attIndex[att] = -1;
			else
				// has problem overflow
				attIndex[att] = m_StartAttIndex[att] + (int) instance.value(att);
		}

		// calculate probabilities for each possible class value
		for (int classVal = 0; classVal < m_NumClasses; classVal++) {
			probs[classVal] = 0;
			numRoot = 0;
			for (int parent = 0; parent < m_NumAttributes; parent++) {
				if (attIndex[parent] == -1 || m_AttCounts[attIndex[parent]] < m_NumRoot)
					continue;
				numRoot++;
				prob = (m_ClassAttAttCounts[classVal][attIndex[parent]][attIndex[parent]] + 1.0)
						/ (m_NumInstances + m_NumClasses * m_NumAttValues[parent]);
				for (int son = 0; son < m_NumAttributes; son++) {
					if (attIndex[son] == -1 || son == parent)
						continue;
					prob *= (m_ClassAttAttCounts[classVal][attIndex[parent]][attIndex[son]] + 1.0)
							/ (m_ClassAttAttCounts[classVal][attIndex[parent]][attIndex[parent]] + m_NumAttValues[son]);
				}
				result[parent][classVal] = prob;
				probs[classVal] += prob;
			}
			if (numRoot >= 1) {
				probs[classVal] /= numRoot;
			} else {
				probs[classVal] = (m_ClassCounts[classVal] + 1.0) / (m_NumInstances + m_NumClasses);
				for (int son = 0; son < m_NumAttributes; son++) {
					if (attIndex[son] == -1)
						continue;
					probs[classVal] *= (m_ClassAttAttCounts[classVal][attIndex[son]][attIndex[son]] + 1.0)
							/ (m_ClassCounts[classVal] + m_NumAttValues[son]);
				}
				for (int parent = 0; parent < m_NumAttributes - 1; parent++) {
					result[parent][classVal] = probs[classVal];
				}
			}
		}

		double[] aa = new double[(m_NumAttributes - 1) * m_NumClasses];
		// double T = 2;
		for (int i = 0; i < m_NumAttributes - 1; i++) {
			Utils.normalize(result[i]);
			// for(int j=0; j<m_NumClasses; j++){
			// result[i][j] = Math.exp(result[i][j]/T);
			// }
			// Utils.normalize(result[i]);
			for (int j = 0; j < m_NumClasses; j++) {
				aa[i * m_NumClasses + j] = result[i][j];
			}
		}

		return aa;
	}

	/**
	 * Calculates the class membership probabilities for the given test instance
	 *
	 * @param instance the instance to be classified
	 * @return predicted class probability distribution
	 * @exception Exception if there is a problem generating the prediction
	 */
	public String[] distributionForInstance4(Instance instance) throws Exception {

		// Definition of local variables
		double[] probs = new double[m_NumClasses];
		double prob;
		int numRoot;

		double[][] result = new double[m_NumAttributes - 1][m_NumClasses];

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
			probs[classVal] = 0;
			numRoot = 0;
			for (int parent = 0; parent < m_NumAttributes; parent++) {
				if (attIndex[parent] == -1 || m_AttCounts[attIndex[parent]] < m_NumRoot)
					continue;
				numRoot++;
				prob = (m_ClassAttAttCounts[classVal][attIndex[parent]][attIndex[parent]] + 1.0)
						/ (m_NumInstances + m_NumClasses * m_NumAttValues[parent]);
				for (int son = 0; son < m_NumAttributes; son++) {
					if (attIndex[son] == -1 || son == parent)
						continue;
					prob *= (m_ClassAttAttCounts[classVal][attIndex[parent]][attIndex[son]] + 1.0)
							/ (m_ClassAttAttCounts[classVal][attIndex[parent]][attIndex[parent]] + m_NumAttValues[son]);
				}
				result[parent][classVal] = prob;
				probs[classVal] += prob;
			}
			if (numRoot >= 1) {
				probs[classVal] /= numRoot;
			} else {
				probs[classVal] = (m_ClassCounts[classVal] + 1.0) / (m_NumInstances + m_NumClasses);
				for (int son = 0; son < m_NumAttributes; son++) {
					if (attIndex[son] == -1)
						continue;
					probs[classVal] *= (m_ClassAttAttCounts[classVal][attIndex[son]][attIndex[son]] + 1.0)
							/ (m_ClassCounts[classVal] + m_NumAttValues[son]);
				}
				for (int parent = 0; parent < m_NumAttributes - 1; parent++) {
					result[parent][classVal] = probs[classVal];
				}
			}
		}

		String[] aa = new String[(m_NumAttributes - 1) * m_NumClasses];
		// double T = 2;
		for (int i = 0; i < m_NumAttributes - 1; i++) {
			Utils.normalize(result[i]);
			double[] result2 = new double[m_NumClasses];
			for (int j = 0; j < m_NumClasses; j++) {
				result2[j] = result[i][j];
			}
			Arrays.sort(result[i]);
			// for(int j=0; j<m_NumClasses; j++){
			// result[i][j] = Math.exp(result[i][j]/T);
			// }
			// Utils.normalize(result[i]);
			for (int j = 0; j < m_NumClasses; j++) {
				for (int k = 0; k < m_NumClasses; k++) {
					if (result2[j] == result[i][k]) {
						aa[i * m_NumClasses + j] = String.valueOf(k + 1);
						break;
					}
				}

			}
		}

		return aa;
	}

	/**
	 * Main method for testing this class.
	 *
	 * @param argv the options
	 */
	public static void main(String[] argv) {

		try {
			System.out.println(Evaluation.evaluateModel(new SPODE(), argv));
		} catch (Exception e) {
			e.printStackTrace();
			System.err.println(e.getMessage());
		}
	}

}
