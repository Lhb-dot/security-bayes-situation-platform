package weka.classifiers.bayes.PMWNB.CAVWNB;

import weka.classifiers.bayes.PMWNB.CAVWNB.BaseWANBObjectiveFunction;
import weka.core.Instance;

public class MSEObjectiveFunction extends BaseWANBObjectiveFunction {
	public MSEObjectiveFunction(int n) {
		super(n);
	}

	@Override
	protected double function(double w[]) {
		double f = 0.0;
		for (int i = 0; i < N; i++) { // iterate over datapoints
			Instance inst = instances.instance(i);
			double p_y[] = condProb(inst, w, i);
			int true_y = (int) inst.classValue();
			for (int y = 0; y < nc; y++) { // iterate over class-labels
				double prod = (ind(y, true_y) - p_y[y]);
				f += (prod * prod);
			}
		}
		return f;
	}

	@Override
	protected double[] gradientFunction(double w[]) {
		double g[] = new double[w.length];
		for (int u = 0; u < g.length; u++) {
			g[u] = 0.0;
		}

		for (int i = 0; i < N; i++) { // iterate over datapoints
			Instance inst = instances.instance(i);
			double p_y[] = condProb(inst, w, i);
			int true_y = (int) inst.classValue();
			for (int c = 0; c < nc; ++c) {
				for (int u = 0; u < cardinalities.length; u++) { // iterate over attributes
					if (inst.attribute(u).isNominal()) {
						if (!inst.isMissing(u)) {
							int x_i = (int) inst.value(u);
							double p = p_y[c];
							double prod = -p * (ind(c, true_y) - p) * (1 - p);

							g[attrValueCounts * c + offset[u] + x_i] += prod * log_theta_UC[u][c][x_i];
						} else {
							double sum = 0.0;
							for (int y2 = 0; y2 < nc; y2++) {
								// sum += p_y[y2] * missing_log_theta_UC[i][y2];

								int missing_value_index = log_theta_UC[u][y2].length - 1;
								sum += p_y[y2] * log_theta_UC[u][y2][missing_value_index];
							}
							for (int y = 0; y < nc; y++) { // iterate over class-labels
								double p = p_y[y];
								double prod = -(ind(y, true_y) - p) * p;

								// g[i] += prod * (missing_log_theta_UC[i][y] - sum);

								int missing_value_index = log_theta_UC[u][y].length - 1;
								g[c * n + u] += prod * (log_theta_UC[u][y][missing_value_index] - sum);
							}
						}
					} else if (inst.attribute(u).isNumeric() && !inst.isMissing(u)) {

						double sum = 0.0;
						for (int y2 = 0; y2 < nc; y2++) {
							// sum += p_y[y2] * Math.log( kEsti[i][y2].getProbability(inst.value(i)) );
							sum += p_y[y2] * log_gamma_UNC[u][y2][i];
						}
						for (int y = 0; y < nc; y++) { // iterate over class-labels
							double p = p_y[y];
							double prod = -(ind(y, true_y) - p) * p;
							// g[i] += prod * (Math.log( kEsti[i][y].getProbability(inst.value(i)) ) - sum);
							g[c * n + u] += prod * (log_gamma_UNC[u][y][i] - sum);
						}
					}

				}
			}
		}
		return g;
	}

	// In a future not so far, this should move to
	// WANBDistrib.distributionForInstance
	protected double[] condProb(Instance inst, double w[], int instIndex) {
		double p_y[] = new double[nc];
		double total = 0;

		for (int y = 0; y < nc; y++) { // iterate over class-labels
			double sum = log_theta_C[y];
			for (int u = 0; u < cardinalities.length; u++) { // iterate over attributes
				if (inst.attribute(u).isNominal()) {
					if (!inst.isMissing(u)) {
						int x_i = (int) inst.value(u);
						int pos = y * attrValueCounts + offset[u] + x_i;
						sum += w[pos] * log_theta_UC[u][y][x_i];
					} else {
						// sum += w[i] * missing_log_theta_UC[i][y];
						int missing_value_index = log_theta_UC[u][y].length - 1;
						sum += w[y * n + u] * log_theta_UC[u][y][missing_value_index];
					}
				} else if (inst.attribute(u).isNumeric() && !inst.isMissing(u)) {
					// sum += w[i] * Math.log( kEsti[i][y].getProbability(inst.value(i)) );
					sum += w[y * n + u] * log_gamma_UNC[u][y][instIndex];
				}
			}

			p_y[y] = Math.exp(sum);
			total += p_y[y];
		}
		// normalize all probs:
		for (int y = 0; y < nc; y++)
			p_y[y] /= total;
		return p_y;
	}

	int ind(int i, int j) {
		return (i == j) ? 1 : 0;
	}

} // ends class
