package weka.classifiers.bayes.PMWNB.CAVWNB;

import java.util.Arrays;

import lbfgsb.FunctionValues;
import weka.classifiers.bayes.PMWNB.CAVWNB.WANBDistribution;
import weka.core.Instances;

public abstract class BaseWANBObjectiveFunction extends BaseObjectiveFunction implements WANBObjectiveFunction {

	protected int N;
	protected int nc;
	protected int cardinalities[];

	// attribute offset array
	protected int offset[];
	// the length of attribute value
	protected int attrValueCounts;
	// m:the number of attributes
	protected int m;

	protected double log_theta_C[];
	protected double log_theta_UC[][][];
	protected double theta_C[];
	protected double theta_UC[][][];
	// protected double missing_log_theta_UC[][];

	protected double log_gamma_UNC[][][];
	protected double gamma_UNC[][][];

	protected double weights[];

	public BaseWANBObjectiveFunction(int n) {
		super(n);
	}

	@Override
	public void init(WANBDistribution distrib, Instances instances2) {
		super.init(distrib, instances2);

		cardinalities = distrib.getCardinalities();

		// n,m:the number of attributes
		n = cardinalities.length;
		m = cardinalities.length;
		int m = instances2.numAttributes();
		// calculate the attribute's offset
		offset = new int[cardinalities.length];
		offset[0] = 0;
		for (int k = 1; k < offset.length; k++) {
			offset[k] = offset[k - 1] + cardinalities[k - 1];
		}
		// the number of attribute value
		attrValueCounts = 0;
		for (int u = 0; u < cardinalities.length; u++) {
			attrValueCounts += cardinalities[u];
		}

		theta_C = distrib.getThetaC();
		nc = theta_C.length;

		theta_UC = distrib.getThetaUC();
		gamma_UNC = distrib.getGammaUNC();
		this.instances = instances2;
		N = instances.numInstances();

		log_theta_C = new double[nc];
		for (int c = 0; c < nc; c++) {
			log_theta_C[c] = Math.log(theta_C[c]);
		}

		log_theta_UC = new double[n][nc][];
		// missing_log_theta_UC = new double[n][nc];
		for (int u = 0; u < n; u++) {
			if (instances.attribute(u).isNominal()) {
				for (int c = 0; c < nc; c++) {
					log_theta_UC[u][c] = new double[cardinalities[u]];
					// missing_log_theta_UC[i][y] = 0;
					for (int v = 0; v < cardinalities[u]; v++) {
						log_theta_UC[u][c][v] = Math.log(theta_UC[u][c][v]);
						// missing_log_theta_UC[i][y] += log_theta_UC[i][y][v];
					}
					// missing_log_theta_UC[i][y] /= cardinalities[i];
				}
			}
		}

		log_gamma_UNC = new double[n][nc][N];
		for (int u = 0; u < n; u++) {
			if (instances.attribute(u).isNumeric()) {
				for (int i = 0; i < N; i++) {
					if (!instances.instance(i).isMissing(u)) {
						for (int c = 0; c < nc; c++)
							log_gamma_UNC[u][c][i] = Math.log(gamma_UNC[u][c][i]);
					} // ends missing val check
				} // ends i
			} // ends numeric check
		} // ends u

	}

	abstract protected double function(double w[]);

	abstract protected double[] gradientFunction(double w[]);

	@Override
	public FunctionValues getValues(double[] w) {
		double oldWeights[] = distrib.getWeights();
		distrib.setWeights(w);
		double fOutput = function(w);
		double grad[] = gradientFunction(w);
		distrib.setWeights(oldWeights);
		return new FunctionValues(fOutput, grad);
	}
}
