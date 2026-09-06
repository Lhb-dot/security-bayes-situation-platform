/*
 *    This program is free software; you can redistribute it and/or modify
 *    it under the terms of the GNU General Public License as published by
 *    the Free Software Foundation; either version 2 of the License, or
 *    (at your option) any later version.
 *
 *    This program is distributed in the hope that it will be useful,
 *    but WITHOUT ANY WARRANTY; without even the implied warranty of
 *    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 *    GNU General Public License for more details.
 *
 *    You should have received a copy of the GNU General Public License
 *    along with this program; if not, write to the Free Software
 *    Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
 */

/*
 *    NaiveBayes.java
 *    Copyright (C) 1999 University of Waikato, Hamilton, New Zealand
 *
 */

package weka.classifiers.zh.CAVWNB;

import weka.classifiers.AbstractClassifier;

import weka.core.Attribute;
import weka.core.Capabilities;
import weka.core.Instance;
import weka.core.Instances;
import weka.core.Option;
import weka.core.OptionHandler;
import weka.core.RevisionUtils;
import weka.core.TechnicalInformation;
import weka.core.TechnicalInformationHandler;
import weka.core.Utils;
import weka.core.WeightedInstancesHandler;
import weka.core.Capabilities.Capability;
import weka.core.TechnicalInformation.Field;
import weka.core.TechnicalInformation.Type;

import weka.estimators.DiscreteEstimator;

import java.util.Enumeration;
import java.util.Vector;

/**
 * <!-- globalinfo-start -->
 * Weighted Naive Bayes - Main class using different weighted version of NB.
 * </pre>
 * <p/>
 * <!-- technical-bibtex-end -->
 *
 * <!-- options-start -->
 * Valid options are:
 * <p/>
 * 
 * <pre>
 *  -D
 *  Use supervised discretization to process numeric attributes
 * </pre>
 * 
 * 
 * e.g.,
 * -D Discretization numeric attributes - MUST be done
 * -O Specify objective function, either MSE or CLL
 * -R Specify regularization, either None or L2
 * 
 * For example
 * -t /home/nayyar/workspace/j_work/weka3-7-5/datasets_O/chess.arff -D
 * -t /home/nayyar/workspace/j_work/weka3-7-5/datasets_O/chess.arff -D -O "MSE"
 * -R "None"
 * <!-- options-end -->
 *
 * @author
 * @version $2.0$
 */
public class CAVWNB extends AbstractClassifier
		implements OptionHandler, WeightedInstancesHandler,
		TechnicalInformationHandler {

	/** for serialization */
	static final long serialVersionUID = 5995231201785697655L;

	/** The attribute estimators. */
	protected DiscreteEstimator[][] m_Distributions;

	/** The class estimator. */
	protected DiscreteEstimator m_ClassDistribution;

	/** The number of attributes in dataset, including class */
	private int m_NumAttributes;

	/** The number of classes (or 1 for numeric class) */
	protected int m_NumClasses;

	/**
	 * The dataset header for the purposes of printing out a semi-intelligible
	 * model
	 */
	protected Instances m_Instances;

	/**
	 * Whether to use discretization than normal distribution
	 * for numeric attributes
	 */
	protected boolean m_UseDiscretization = false;

	/** The discretization filter */
	protected weka.filters.supervised.attribute.Discretize m_Disc = null;

	/** The weighted naive Bayes distribution */
	protected WANBDistribution distrib;

	/** The weights to be optimized for naive Bayes */
	private double[] m_AttWeights;

	/** Default Objective Function */
	private String objectiveFunction = "CLL";

	/** Default Regularizer */
	private String regularizer = "L2";

	/** L2 regularization coefficient (lambda). */
	private double regularizationLambda = 1.0;

	public WANBDistribution geDistribution() {
		return distrib;
	}

	public DiscreteEstimator getClassDiscreteEstimator() {
		return m_ClassDistribution;
	}
	
	/**
	 * Generates the classifier.
	 *
	 * @param instances set of instances serving as training data
	 * @exception Exception if the classifier has not been generated
	 *                      successfully
	 */
	@Override
	public void buildClassifier(Instances instances) throws Exception {

		// can classifier handle the data?
		getCapabilities().testWithFail(instances);

		// remove instances with missing class
		instances = new Instances(instances);
		instances.deleteWithMissingClass();

		m_NumClasses = instances.numClasses();
		m_NumAttributes = instances.numAttributes();
		// Copy the instances
		m_Instances = new Instances(instances);

		int numInstances = instances.numInstances();

		// Discretize instances if required
		if (m_UseDiscretization) {
			m_Disc = new weka.filters.supervised.attribute.Discretize();
			m_Disc.setInputFormat(m_Instances);
			m_Instances = weka.filters.Filter.useFilter(m_Instances, m_Disc);
		} else {
			m_Disc = null;
		}

		// Reserve space for Attribute distributions
		m_Distributions = new DiscreteEstimator[m_Instances.numAttributes() - 1][m_Instances.numClasses()];

		// Reserve space for Class distribution
		m_ClassDistribution = new DiscreteEstimator(m_Instances.numClasses(), false);

		int att = 0;
		Enumeration enu = m_Instances.enumerateAttributes();
		while (enu.hasMoreElements()) {
			Attribute attribute = (Attribute) enu.nextElement();

			for (int c = 0; c < m_Instances.numClasses(); c++) {
				switch (attribute.type()) {
					case Attribute.NUMERIC:
						throw new Exception("Can't handle numeric attributes");
					case Attribute.NOMINAL:
						m_Distributions[att][c] = new DiscreteEstimator(attribute.numValues() + 1, false);
						// +1 is for missing attributes
						break;
					default:
						throw new Exception("Attribute type unknown to NaiveBayes");
				}
			}
			att++;

		}
		int ii = 0;
		// Compute counts
		Enumeration enumInsts = m_Instances.enumerateInstances();
		while (enumInsts.hasMoreElements()) {
			Instance instance = (Instance) enumInsts.nextElement();
			ii++;
			updateClassifier(instance);
			// System.out.println(ii);
		}

		distrib = new WANBDistribution(m_ClassDistribution, m_Distributions);

		WeightComputer wc;

		// the number of attribute value
		int[] cardinalities = distrib.getCardinalities();
		int attrValueCounts = 0;
		for (int i = 0; i < cardinalities.length; i++) {
			attrValueCounts += cardinalities[i];
		}

		WANBObjectiveFunction obj = new RegularizedObjectiveFunctionFactory().getObjectiveFunction(objectiveFunction,
				regularizer, attrValueCounts * m_NumClasses, regularizationLambda);

		BaseWeightComputer bwc = new BaseWeightComputer();
		bwc.setObjectiveFunction(obj);
		wc = bwc;

		m_AttWeights = wc.assessWeights(distrib, m_Instances);

		// Set the distribution weights
		distrib.setWeights(m_AttWeights);

		/*
		 * for(int i = 0; i <m_AttWeights.length; i++)
		 * {
		 * System.out.printf("%.4f &", m_AttWeights[i]);
		 * }
		 * System.out.println();
		 */
		/*
		 * for(int i = 0; i <m_AttWeights.length/3; i++)
		 * {
		 * System.out.printf("%.4f &", m_AttWeights[i]);
		 * }
		 * System.out.println();
		 * for(int i = m_AttWeights.length/3; i <m_AttWeights.length*2/3; i++)
		 * {
		 * System.out.printf("%.4f &", m_AttWeights[i]);
		 * }
		 * System.out.println();
		 * for(int i = m_AttWeights.length*2/3; i <m_AttWeights.length; i++)
		 * {
		 * System.out.printf("%.4f &", m_AttWeights[i]);
		 * }
		 * System.out.println();
		 * System.out.println();
		 */

		// Save space
		m_Instances = new Instances(m_Instances, 0);

	}

	/**
	 * Updates the classifier with the given instance.
	 *
	 * @param instance the new training instance to include in the model
	 * @exception Exception if the instance could not be incorporated in
	 *                      the model.
	 */
	public void updateClassifier(Instance instance) throws Exception {

		if (!instance.classIsMissing()) {
			Enumeration enumAtts = m_Instances.enumerateAttributes();
			int att = 0;
			while (enumAtts.hasMoreElements()) {
				Attribute attribute = (Attribute) enumAtts.nextElement();
				if (instance.attribute(att).isNominal()) {
					if (!instance.isMissing(attribute))
						m_Distributions[att][(int) instance.classValue()].addValue(instance.value(attribute),
								instance.weight());
					else
						m_Distributions[att][(int) instance.classValue()].addValue(attribute.numValues(),
								instance.weight());
					// System.out.println("att"+att+" "+instance.value(attribute));

				}
				att++;
			}
			m_ClassDistribution.addValue(instance.classValue(), instance.weight());
		}

	}

	/**
	 * Calculates the class membership probabilities for the given test
	 * instance.
	 *
	 * @param instance the instance to be classified
	 * @return predicted class probability distribution
	 * @exception Exception if there is a problem generating the prediction
	 */
	@Override
	public double[] distributionForInstance(Instance instance) throws Exception {

		// System.out.println(instance);
		if (m_UseDiscretization) {
			m_Disc.input(instance);
			instance = m_Disc.output();
		}

		return distrib.distributionForInstance(instance);
	}

	/**
	 * Per-instance binary log-odds evidence decomposition (weighted NB terms).
	 * Same preprocessing as {@link #distributionForInstance(Instance)} (e.g.
	 * supervised discretization when enabled). Requires a two-class problem at
	 * training time; semantics match
	 * {@link WANBDistribution#evidenceWeightForBinaryClassification(Instance)}.
	 *
	 * @param instance the instance to decompose
	 * @return {@code ans[0..n-1]}: per-attribute
	 *         {@code w0*log P(x_u|c0)-w1*log P(x_u|c1)}; {@code ans[n]}:
	 *         {@code log P(c0)-log P(c1)}; {@code n} is the number of
	 *         non-class attributes
	 * @exception Exception if the model is not applicable or binary check fails
	 */
	public double[] evidenceWeightForBinaryClassification(Instance instance) throws Exception {

		if (m_UseDiscretization) {
			m_Disc.input(instance);
			instance = m_Disc.output();
		}

		return distrib.evidenceWeightForBinaryClassification(instance);
	}

	// ------------------------------------------------------------------------
	// Weka Functions
	// ------------------------------------------------------------------------

	/**
	 * Returns a string describing this classifier
	 * 
	 * @return a description of the classifier suitable for
	 *         displaying in the explorer/experimenter gui
	 */
	public String globalInfo() {
		return "Class for a weighted Naive Bayes classifier using estimator classes. " +
				"More Information to be added here. Technical information:\n\n"
				+ getTechnicalInformation().toString();
	}

	/**
	 * Returns an instance of a TechnicalInformation object, containing
	 * detailed information about the technical background of this class,
	 * e.g., paper reference or book this class is based on.
	 * 
	 * @return the technical information about this class
	 */
	@Override
	public TechnicalInformation getTechnicalInformation() {
		TechnicalInformation result;

		result = new TechnicalInformation(Type.INPROCEEDINGS);
		result.setValue(Field.AUTHOR, "Nayyar Zaidi , Jesus Cerquides, Mark Carman, Geoffrey I. Webb");
		result.setValue(Field.TITLE, "Obviating Naive Bayes Attribute Independence Assumption by Attribute Weighting");
		result.setValue(Field.BOOKTITLE, "in writing");
		result.setValue(Field.YEAR, "");
		result.setValue(Field.PAGES, "");
		result.setValue(Field.PUBLISHER, "");
		result.setValue(Field.ADDRESS, "");

		return result;
	}

	/**
	 * Returns default capabilities of the classifier.
	 *
	 * @return the capabilities of this classifier
	 */
	@Override
	public Capabilities getCapabilities() {
		Capabilities result = super.getCapabilities();
		result.disableAll();

		// attributes
		result.enable(Capability.NUMERIC_ATTRIBUTES);
		result.enable(Capability.NOMINAL_ATTRIBUTES);
		result.enable(Capability.MISSING_VALUES);

		// class
		result.enable(Capability.NOMINAL_CLASS);
		result.enable(Capability.MISSING_CLASS_VALUES);

		// instances
		result.setMinimumNumberInstances(0);

		return result;
	}

	/**
	 * Returns an enumeration describing the available options.
	 *
	 * @return an enumeration of all the available options.
	 */
	@Override
	public Enumeration listOptions() {

		Vector newVector = new Vector(3);

		// newVector.addElement(
		// new Option("\tUse supervised discretization to process numeric attributes\n",
		// "D", 0,"-D"));

		newVector.addElement(
				new Option("\tDisplay model in old format (good when there are " + "many classes)\n", "O", 0, "-O"));
		newVector.addElement(
				new Option("\tSpecify Regularizer (either None or L2)\n", "R", 1, "-R <None|L2>"));
		newVector.addElement(
				new Option("\tSpecify regularization coefficient lambda for L2 (default: 1.0)\n", "L", 1, "-L <double>"));

		return newVector.elements();
	}

	/**
	 * Parses a given list of options.
	 * <p/>
	 *
	 * <!-- options-start -->
	 * Valid options are:
	 * <p/>
	 * 
	 * <pre>
	 *  -D
	 *  Use supervised discretization to process numeric attributes
	 * </pre>
	 *
	 * <pre>
	 *  -O
	 *  Specify Objective Function (either MSE or CLL)
	 * </pre>
	 * 
	 * <pre>
	 *  -R
	 *  Specify Regularizer (either None or L2)
	 * </pre>
	 * 
	 * <pre>
	 *  -L
	 *  Specify regularization coefficient lambda for L2
	 * </pre>
	 * 
	 * <!-- options-end -->
	 *
	 * @param options the list of options as an array of strings
	 * @exception Exception if an option is not supported
	 */
	@Override
	public void setOptions(String[] options) throws Exception {

		// boolean d = Utils.getFlag('D', options);

//		 setUseSupervisedDiscretization(d);

		String wScheme = Utils.getOption('O', options);
		if (wScheme.length() != 0) {
			setObjectiveFunction(wScheme);
		}

		String reg = Utils.getOption('R', options);
		if (reg.length() != 0) {
			setRegularizer(reg);
		}

		String lambda = Utils.getOption('L', options);
		if (lambda.length() != 0) {
			setRegularizationLambda(Double.parseDouble(lambda));
		}

		// Utils.checkForRemainingOptions(options);
	}

	/**
	 * Gets the current settings of the classifier.
	 *
	 * @return an array of strings suitable for passing to setOptions
	 */
	@Override
	public String[] getOptions() {

		String[] options = new String[8];
		int current = 0;

		/*
		 * if (m_UseDiscretization) {
		 * options[current++] = "-D";
		 * }
		 */

		// options[current++] = "-D";
		// options[current++] = "" + getUseSupervisedDiscretization();

		options[current++] = "-O";
		options[current++] = "" + getObjectiveFunction();

		options[current++] = "-R";
		options[current++] = "" + getRegularizer();

		options[current++] = "-L";
		options[current++] = "" + getRegularizationLambda();

		while (current < options.length) {
			options[current++] = "";
		}
		return options;
	}

	/**
	 * Returns a description of the classifier.
	 *
	 * @return a description of the classifier as a string.
	 */
	@Override
	public String toString() {
		StringBuffer text = new StringBuffer();

		text.append("Naive Bayes Classifier");
		if (m_Instances == null) {
			text.append(": No model built yet.");
		} else {
			try {
				for (int i = 0; i < m_Distributions[0].length; i++) {
					text.append("\n\nClass " + m_Instances.classAttribute().value(i) +
							": Prior probability = " + Utils.doubleToString(m_ClassDistribution.getProbability(i),
									4, 2)
							+ "\n\n");
					Enumeration enumAtts = m_Instances.enumerateAttributes();
					int attIndex = 0;
					while (enumAtts.hasMoreElements()) {
						Attribute attribute = (Attribute) enumAtts.nextElement();
						if (attribute.weight() > 0) {
							text.append(attribute.name() + ":  "
									+ m_Distributions[attIndex][i]);
						}
						attIndex++;
					}
				}
			} catch (Exception ex) {
				text.append(ex.getMessage());
			}
		}

		return text.toString();

	}

	// ------------------------------------------------------------------------
	// Bean Functions
	// ------------------------------------------------------------------------

	/**
	 * Get m_AttWeights - weights used to optimize naive Bayes weights.
	 *
	 * @return double[] m_AttWeights
	 */
	public double[] getWeights() {
		return m_AttWeights;
	}

	/**
	 * Set m_AttWeights - weigths used to optimize naive Bayes weights in S1 scheme.
	 *
	 * @param s String for S1 weights.
	 */
	public void setWeights(double[] w) {
		m_AttWeights = w;
	}

	/**
	 * Get m_wScheme (scheme) used to optimize naive Bayes weights.
	 *
	 * @return String m_wScheme used for weighting.
	 */
	public String getObjectiveFunction() {
		return objectiveFunction;
	}

	/**
	 * Set m_wScheme used to optimize naive Bayes weights.
	 *
	 * @param v wScheme.
	 */
	public void setObjectiveFunction(String o) {
		this.objectiveFunction = o;
	}

	/**
	 * Get m_wScheme (scheme) used to optimize naive Bayes weights.
	 *
	 * @return String m_wScheme used for weighting.
	 */
	public String getRegularizer() {
		return regularizer;
	}

	/**
	 * Set m_wScheme used to optimize naive Bayes weights.
	 *
	 * @param v wScheme.
	 */
	public void setRegularizer(String r) {
		this.regularizer = r;
	}

	public double getRegularizationLambda() {
		return regularizationLambda;
	}

	public void setRegularizationLambda(double lambda) {
		this.regularizationLambda = lambda;
	}

	/**
	 * Get whether supervised discretization is to be used.
	 *
	 * @return true if supervised discretization is to be used.
	 */
	public boolean getUseSupervisedDiscretization() {
		return m_UseDiscretization;
	}

	/**
	 * Set whether supervised discretization is to be used.
	 *
	 * @param newblah true if supervised discretization is to be used.
	 */
	public void setUseSupervisedDiscretization(boolean flag) {
		m_UseDiscretization = flag;
	}

	/**
	 * Returns the revision string.
	 * 
	 * @return the revision
	 */
	@Override
	public String getRevision() {
		return RevisionUtils.extract("$Revision: 5928 $");
	}

	/**
	 * Main method for testing this class.
	 *
	 * @param argv the options
	 */
	public static void main(String[] argv) {
		runClassifier(new CAVWNB(), argv);
	}

	public double[] buildClassifier3(Instances instances, double[] weight111) throws Exception {

		// can classifier handle the data?
		getCapabilities().testWithFail(instances);

		// remove instances with missing class
		instances = new Instances(instances);
		instances.deleteWithMissingClass();

		m_NumClasses = instances.numClasses();
		m_NumAttributes = instances.numAttributes();
		// Copy the instances
		m_Instances = new Instances(instances);

		int numInstances = instances.numInstances();

		// Discretize instances if required
		if (m_UseDiscretization) {
			m_Disc = new weka.filters.supervised.attribute.Discretize();
			m_Disc.setInputFormat(m_Instances);
			m_Instances = weka.filters.Filter.useFilter(m_Instances, m_Disc);
		} else {
			m_Disc = null;
		}

		// Reserve space for Attribute distributions
		m_Distributions = new DiscreteEstimator[m_Instances.numAttributes() - 1][m_Instances.numClasses()];

		// Reserve space for Class distribution
		m_ClassDistribution = new DiscreteEstimator(m_Instances.numClasses(), false);

		int att = 0;
		Enumeration enu = m_Instances.enumerateAttributes();
		while (enu.hasMoreElements()) {
			Attribute attribute = (Attribute) enu.nextElement();

			for (int c = 0; c < m_Instances.numClasses(); c++) {
				switch (attribute.type()) {
					case Attribute.NUMERIC:
						throw new Exception("Can't handle numeric attributes");
					case Attribute.NOMINAL:
						m_Distributions[att][c] = new DiscreteEstimator(attribute.numValues()+1, false);
						// +1 is for missing attributes !
						break;
					default:
						throw new Exception("Attribute type unknown to NaiveBayes");
				}
			}
			att++;

		}

		// Compute counts
		Enumeration enumInsts = m_Instances.enumerateInstances();
		while (enumInsts.hasMoreElements()) {
			Instance instance = (Instance) enumInsts.nextElement();
			updateClassifier(instance);
		}

		distrib = new WANBDistribution(m_ClassDistribution, m_Distributions);

		distrib.setWeights(weight111);
		WeightComputer wc;

		// the number of attribute value
		int[] cardinalities = distrib.getCardinalities();
		int attrValueCounts = 0;
		for (int i = 0; i < cardinalities.length; i++) {
			attrValueCounts += cardinalities[i];
		}

		WANBObjectiveFunction obj = new RegularizedObjectiveFunctionFactory().getObjectiveFunction(objectiveFunction,
				regularizer, attrValueCounts * m_NumClasses, regularizationLambda);

		BaseWeightComputer bwc = new BaseWeightComputer();
		bwc.setObjectiveFunction(obj);
		wc = bwc;

		m_AttWeights = wc.assessWeights(distrib, m_Instances);

		// Set the distribution weights
		distrib.setWeights(m_AttWeights);

		/*
		 * for(int i = 0; i <m_AttWeights.length; i++)
		 * {
		 * System.out.printf("%.4f &", m_AttWeights[i]);
		 * }
		 * System.out.println();
		 */
		/*
		 * for(int i = 0; i <m_AttWeights.length/3; i++)
		 * {
		 * System.out.printf("%.4f &", m_AttWeights[i]);
		 * }
		 * System.out.println();
		 * for(int i = m_AttWeights.length/3; i <m_AttWeights.length*2/3; i++)
		 * {
		 * System.out.printf("%.4f &", m_AttWeights[i]);
		 * }
		 * System.out.println();
		 * for(int i = m_AttWeights.length*2/3; i <m_AttWeights.length; i++)
		 * {
		 * System.out.printf("%.4f &", m_AttWeights[i]);
		 * }
		 * System.out.println();
		 * System.out.println();
		 */

		// Save space
		m_Instances = new Instances(m_Instances, 0);

		return m_AttWeights;

	}

}
