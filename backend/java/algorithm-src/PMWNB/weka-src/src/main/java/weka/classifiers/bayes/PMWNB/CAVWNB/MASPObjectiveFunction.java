package weka.classifiers.bayes.PMWNB.CAVWNB;

import java.util.Enumeration;

import weka.classifiers.bayes.PMWNB.CAVWNB.BaseWANBObjectiveFunction;
import weka.classifiers.bayes.PMWNB.CAVWNB.WANBDistribution;
import weka.core.Attribute;
import weka.core.Instance;
import weka.core.Instances;

public class MASPObjectiveFunction extends BaseWANBObjectiveFunction {
	private double logFSP;
	private double theta_UC_exp[][][];
	private double gamma_UNC_exp[][][];
	// private double missing_theta_UC_exp[][];
	private double Q[][];
	private double R[];

	public MASPObjectiveFunction(int n) {
		super(n);
	}

	@Override
	public void init(WANBDistribution distrib, Instances instances) {
		super.init(distrib, instances);

		theta_UC_exp = new double[m][nc][];
		gamma_UNC_exp = new double[m][nc][N];
		// missing_theta_UC_exp = new double[n][nc];
		for (int u = 0; u < m; u++) {
			// theta_UC_exp[u] = new double [nc][];
			if (instances.attribute(u).isNominal()) {
				for (int c = 0; c < nc; c++) {
					theta_UC_exp[u][c] = new double[cardinalities[u]];
				}
			}
		}

		R = new double[N];
		Q = new double[N][nc];
	}

	protected void assessExps(double w[]) {

		for (int u = 0; u < m; u++) {
			if (instances.attribute(u).isNominal()) {
				for (int c = 0; c < nc; c++) {
					for (int i = 0; i < cardinalities[u]; i++) {
						int pos = c * attrValueCounts + offset[u] + i;
						theta_UC_exp[u][c][i] = Math.exp(log_theta_UC[u][c][i] * w[pos]);
					}
					// missing_theta_UC_exp[u][c] = Math.exp(missing_log_theta_UC[u][c] * w[u]);
				}
			} else if (instances.attribute(u).isNumeric()) {
				for (int i = 0; i < N; i++) {
					if (!instances.instance(i).isMissing(u)) {
						for (int c = 0; c < nc; c++)
							gamma_UNC_exp[u][c][i] = Math.exp(log_gamma_UNC[u][c][i] * w[c * n + u]);
					} // ends missing val check
				} // ends i
			}
		}

	}

	protected double assessQsRsandLogFSP() {
		Instance inst;
		double p;
		int x_u;
		double logFSP = 0.0;
		for (int i = 0; i < N; i++) {
			R[i] = 0.0;
			inst = instances.instance(i);
			for (int c = 0; c < nc; c++) {
				p = theta_C[c];
				Enumeration enumAtts = inst.enumerateAttributes();
				int u = 0;
				while (enumAtts.hasMoreElements()) {
					Attribute attribute = (Attribute) enumAtts.nextElement();

					if (inst.attribute(u).isNominal()) {

						if (!inst.isMissing(attribute)) {
							x_u = (int) inst.value(attribute);
							p *= theta_UC_exp[u][c][x_u];
						} else {
							// p *= missing_theta_UC_exp[u][c];
							int missingValueIndex = theta_UC_exp[u][c].length - 1;
							p *= theta_UC_exp[u][c][missingValueIndex];
						}

					} else if (inst.attribute(u).isNumeric() && !inst.isMissing(u)) {
						p *= gamma_UNC_exp[u][c][i];
					}
					u++;
				}
				Q[i][c] = p;
				R[i] += p;
			}
			int x_C = (int) inst.classValue();
			logFSP += Math.log(Q[i][x_C]) - Math.log(R[i]);
		} // ends j

		return -logFSP;
	}

	@Override
	protected double function(double[] w) {
		assessExps(w);
		logFSP = assessQsRsandLogFSP();
		return logFSP;
	}

	@Override
	protected double[] gradientFunction(double[] w) {

		double G[] = new double[attrValueCounts * nc];
		Instance inst;
		int x_u, x_C;

		for (int u = 0; u < G.length; u++) {
			G[u] = 0.0;
		}

		for (int i = 0; i < N; i++) {

			inst = instances.instance(i);
			x_C = (int) inst.classValue();
			for (int c = 0; c < nc; ++c) {
				Enumeration enumAtts = inst.enumerateAttributes();
				int u = 0;
				while (enumAtts.hasMoreElements()) {
					Attribute attribute = (Attribute) enumAtts.nextElement();

					if (inst.attribute(u).isNominal()) {

						int missingValueIndex = theta_UC_exp[u][x_C].length - 1;

						if (!inst.isMissing(attribute)) {
							x_u = (int) inst.value(attribute);
							double tmp = 0.0;
							tmp = (ind(c, x_C) - Q[i][c] / R[i]) * log_theta_UC[u][c][x_u];
							// calculate the position
							int pos = c * attrValueCounts + offset[u] + x_u;
							G[pos] -= tmp;
						} else {
							// G[u] -= missing_log_theta_UC[u][x_C];
							G[c * n + u] -= log_theta_UC[u][x_C][missingValueIndex];
							double tmp = 0.0;
							for (int c1 = 0; c1 < nc; c1++) {
								// tmp += Q[j][c] * missing_log_theta_UC[u][c];
								tmp += Q[i][c1] * log_theta_UC[u][c1][missingValueIndex];
							}
							tmp /= R[i];
							G[c * n + u] += tmp;
						}

					} else if (inst.attribute(u).isNumeric() && !inst.isMissing(u)) {

						G[u] -= log_gamma_UNC[u][x_C][i];
						double tmp = 0.0;
						for (int c1 = 0; c1 < nc; c1++) {
							tmp += Q[i][c1] * log_gamma_UNC[u][c1][i];
						}
						tmp /= R[i];
						G[u] += tmp;

					}

					u++;
				}
			}
		}
		return G;
	}

	int ind(int i, int j) {
		return (i == j) ? 1 : 0;
	}
} // ends class
