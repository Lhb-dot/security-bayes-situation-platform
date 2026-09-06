package weka.classifiers.bayes.PMWNB.CAVWNB;

import java.io.Serializable;
import java.util.Arrays;
import java.util.Enumeration;

import weka.core.Attribute;
import weka.core.Instance;
import weka.core.Utils;

import weka.estimators.DiscreteEstimator;

public class WANBDistribution implements Serializable {

	private int n;
	private int N;
	private int nc;

	// the number of attribute value
	private int attrValueCounts = 0;

	private int cardinalities[];
	private double weights[];

	private double theta_C[];
	private double theta_UC[][][];

	private double logtheta_C[];
	private double logtheta_UC[][][];

	private double gamma_UNC[][][];
	private int offset[];

	/*
	 * Original Constructor: Called when all attributes are nominal
	 * m_ClassDistribution: Class Estimator m_Distributions: Nominal Estimators
	 * for attributes
	 */
	public WANBDistribution(DiscreteEstimator m_ClassDistribution, DiscreteEstimator[][] m_Distributions) {

		nc = m_ClassDistribution.getNumSymbols();
		n = m_Distributions.length;

		theta_C = new double[nc];
		theta_UC = new double[n][nc][];

		logtheta_C = new double[nc];
		logtheta_UC = new double[n][nc][];

		cardinalities = new int[n];

		for (int u = 0; u < n; u++) {
			DiscreteEstimator dEsti = m_Distributions[u][0];
			cardinalities[u] = dEsti.getNumSymbols() - 1;
			attrValueCounts += cardinalities[u]; // attribute value counts
			for (int c = 0; c < nc; c++) {
				theta_UC[u][c] = new double[cardinalities[u]];
				logtheta_UC[u][c] = new double[cardinalities[u]];
			}
		}

		weights = new double[attrValueCounts * nc];

		/* Initialize the arrays */
		for (int u = 0; u < weights.length; u++) {
			weights[u] = 1.0;
		}

		for (int c = 0; c < nc; c++) {
			theta_C[c] = m_ClassDistribution.getProbability_laplace(c);
			logtheta_C[c] = Math.log(theta_C[c]);
		}

		for (int u = 0; u < n; u++) {
			for (int c = 0; c < nc; c++) {
				for (int i = 0; i < cardinalities[u]; i++) {
					theta_UC[u][c][i] = m_Distributions[u][c].getProbability_laplace(i);
					logtheta_UC[u][c][i] = Math.log(Math.max(theta_UC[u][c][i], 1e-75));
				}
			}
		}

		// calculate the attribute's offset (wsy)
		offset = new int[cardinalities.length];
		for (int k = 1; k < offset.length; k++) {
			offset[k] = offset[k - 1] + cardinalities[k - 1];
		}

	}

	/*
	 * Distribution for instance: This is different from original
	 * distributionforinstance() function in main class. This function will
	 * assume that attribute values are infact the probabililties.
	 */
	public double[] distributionForInstance(Instance instance) throws Exception {

		double[] probs = new double[nc];

		for (int c = 0; c < nc; c++) {
			probs[c] = logtheta_C[c];
		}

		// calculate the attribute's offset
		offset = new int[cardinalities.length];
		for (int k = 1; k < offset.length; k++) {
			offset[k] = offset[k - 1] + cardinalities[k - 1];
		}

		Enumeration enumAtts = instance.enumerateAttributes();
		int u = 0;
		while (enumAtts.hasMoreElements()) {
			Attribute attribute = (Attribute) enumAtts.nextElement();
			if (!instance.isMissing(attribute)) {
				double max = 0;
				for (int c = 0; c < nc; c++) {
					if (instance.attribute(u).isNominal()) {
						probs[c] += weights[attrValueCounts * c + offset[u] + (int) instance.value(attribute)]
								* logtheta_UC[u][c][(int) instance.value(attribute)];
					}

					if (probs[c] > max)
						max = probs[c];

					if (Double.isNaN(probs[c]) || Double.isInfinite(probs[c])) {
						throw new Exception("NaN or Infinity returned from estimator for attribute "
								+ attribute.name() + ":\n" + getThetaUC()[u][c].toString());
					}
				}
				if ((max > 0) && (max < 1e-75)) { // Danger of probability underflow
					for (int c = 0; c < nc; c++)
						probs[c] *= 1e75;
				}
			}
			u++;
		}

		double sum = 0;
		for (int c = 0; c < nc; c++) {
			probs[c] = Math.exp(probs[c]);
			sum += probs[c];
		}

		if (sum == 0) {
			System.out.println("tintin");
			for (int c = 0; c < nc; c++)
				probs[c] = 1e-75;
		}

		// Display probabilities
		Utils.normalize(probs);
		return probs;

	}

	public int[] getOffset() {
		return offset;
	}

	public void setWeights(double[] newWeights) {
		weights = newWeights;
	}

	public double[] getWeights() {
		return weights;
	}

	public double[][][] getThetaUC() {
		return theta_UC;
	}

	public int getAttValueCounts() {
		return attrValueCounts;
	}

	public double[][][] getGammaUNC() {
		return gamma_UNC;
	}

	public int[] getCardinalities() {
		return cardinalities;
	}

	public double[] getThetaC() {
		return theta_C;
	}

}
