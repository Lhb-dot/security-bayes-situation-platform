package weka.classifiers.bayes.PMWNB.CAVWNB;

import weka.classifiers.bayes.PMWNB.CAVWNB.BaseObjectiveFunction;
import weka.classifiers.bayes.PMWNB.CAVWNB.WANBObjectiveFunction;

import lbfgsb.FunctionValues;

public class EmptyRegularizer extends BaseObjectiveFunction implements WANBObjectiveFunction {
	public EmptyRegularizer(int dimensions) {
		super(dimensions);
	}

	@Override
	public FunctionValues getValues(double[] w) {
		double grad[] = new double[w.length];
		double regF = 0.0;
		return new FunctionValues(regF, grad);
	}
}
