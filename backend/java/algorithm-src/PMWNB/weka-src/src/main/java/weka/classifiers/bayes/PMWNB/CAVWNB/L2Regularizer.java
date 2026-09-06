package weka.classifiers.bayes.PMWNB.CAVWNB;

import weka.classifiers.bayes.PMWNB.CAVWNB.BaseObjectiveFunction;
import weka.classifiers.bayes.PMWNB.CAVWNB.WANBObjectiveFunction;

import lbfgsb.FunctionValues;

public class L2Regularizer extends BaseObjectiveFunction implements WANBObjectiveFunction {

	private double lambda = 1.0;
	private double mu = 1.0;

	public L2Regularizer(int dimensions) {
		super(dimensions);
	}

	@Override
	public FunctionValues getValues(double[] w) {
		double grad[] = new double[w.length];
		double regF = 0.0;
		for (int i = 0; i < w.length; i++) {
			double weight = w[i] - mu;
			// System.out.println(weight);
			regF += lambda * weight * weight;
			// System.out.println(fOutput);
			grad[i] = 2.0 * lambda * weight;
		}

		// System.out.println("w="+Arrays.toString(w));
		// System.out.println("L2 Reg = "+regF);
		// System.out.println("L2 Reg grad = "+Arrays.toString(grad));
		// System.out.println("-------------------------");

		return new FunctionValues(regF, grad);
	}
}
