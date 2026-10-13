/*
 *    FLNB_poly.java
 */

package weka.classifiers.bayes;

import weka.classifiers.AbstractClassifier;
import weka.core.Instance;
import weka.core.Instances;
import weka.core.Utils;

public class FLNB_poly extends AbstractClassifier {

	/** for serialization */
	static final long serialVersionUID = -4503874444306113214L;

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

	/** The training instances used for classification. */
	private Instances m_Train;

	private double[][] m_ClassAttWeights;
	private double[] m_ClassWeights;
	private double m_WeightSum;
	
	/** The number of each attribute value occurs in the dataset */
	private double[] m_AttCounts;

	/**
	 * Generates the classifier.
	 *
	 * @param instances set of instances serving as training data
	 * @exception Exception if the classifier has not been generated successfully
	 */
	public void buildClassifier(Instances instances) throws Exception {
		
		//System.out.println(instances.toString());

		m_Train = new Instances(instances);

		// can classifier handle the data?
		getCapabilities().testWithFail(instances);

		// remove instances with missing class
		instances = new Instances(instances);
		instances.deleteWithMissingClass();

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

		// Count global occurrences of each attribute value
		m_AttCounts = new double[m_TotalAttValues];
		for (int i = 0; i < m_NumInstances; i++) {
			int[] attIndex = new int[m_NumAttributes];
			for (int j = 0; j < m_NumAttributes; j++) {
				attIndex[j] = m_StartAttIndex[j] + (int) instances.instance(i).value(j);
				m_AttCounts[attIndex[j]]++;
			}
		}

		// polynomial formulation
		for (int i = 0; i < m_TotalAttValues; i++) {
			m_AttCounts[i] /= m_NumInstances;
			m_AttCounts[i] = 1 - m_AttCounts[i];
		}
		
		//System.out.println("Arrays:" + Arrays.toString(m_AttCounts));

	}

	/**
	 * Calculates the class membership probabilities for the given test instance
	 *
	 * @param instance the instance to be classified
	 * @return predicted class probability distribution
	 * @exception Exception if there is a problem generating the prediction
	 */
	public double[] distributionForInstance(Instance instance) throws Exception {

		// Calculate the similarity
		double similarity;
		for (int i = 0; i < m_NumInstances; i++) {
			similarity = similarity(instance, m_Train.instance(i));
			//System.out.println("instance:"+i +" similarity=" + similarity);
			m_Train.instance(i).setWeight(similarity);
		}

		// Calculate the counts
		// allocate space for counts and frequencies
		m_ClassWeights = new double[m_NumClasses];
		m_ClassAttWeights = new double[m_NumClasses][m_TotalAttValues];
		for (int k = 0; k < m_NumInstances; k++) {
			int classVal = (int) m_Train.instance(k).classValue();
			m_ClassWeights[classVal] += m_Train.instance(k).weight();
			m_WeightSum += m_Train.instance(k).weight();
			int[] attIndex = new int[m_NumAttributes];
			for (int i = 0; i < m_NumAttributes; i++) {
				if (i == m_ClassIndex) {
					attIndex[i] = -1;
				} else {
					attIndex[i] = m_StartAttIndex[i] + (int) m_Train.instance(k).value(i);
					m_ClassAttWeights[classVal][attIndex[i]] += m_Train.instance(k).weight();
				}
			}
		}

		// Definition of local variables
		double[] probs = new double[m_NumClasses];
		// store instance's att values in an int array
		int[] attIndex = new int[m_NumAttributes];
		for (int att = 0; att < m_NumAttributes; att++) {
			attIndex[att] = m_StartAttIndex[att] + (int) instance.value(att);
		}
		// calculate probabilities for each possible class value
		for (int classVal = 0; classVal < m_NumClasses; classVal++) {
			probs[classVal] = (m_ClassWeights[classVal] + 1.0 / m_NumClasses) / (m_WeightSum + 1.0);
			for (int att = 0; att < m_NumAttributes; att++) {
				if (att == m_ClassIndex)
					continue;
				probs[classVal] *= (m_ClassAttWeights[classVal][attIndex[att]] + 1.0 / m_NumAttValues[att])
						/ (m_ClassWeights[classVal] + 1.0);
			}
		}
		Utils.normalize(probs);
		return probs;
	}

	/**
	 * Main method for testing this class.
	 *
	 * @param args the options
	 */
	public static void main(String[] args) {
		runClassifier(new FLNB_poly(), args);
	}

	/**
	 * Calculates the similarity between two instances
	 *
	 * @param first  the first instance
	 * @param second the second instance
	 * @return the similarity between the two given instances
	 */
	private double similarity(Instance first, Instance second) {

		double similarity = 0;
		for (int i = 0; i < m_NumAttributes; i++) {
			if (i == m_ClassIndex)
				continue;
			int firstValue = (int) first.value(i);
			int secondValue = (int) second.value(i);
			if (firstValue == secondValue) {
				similarity += m_AttCounts[m_StartAttIndex[i] + firstValue];
			}
		}
		return similarity;
	}
}
