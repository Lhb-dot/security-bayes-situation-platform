package weka.classifiers.zh.CAVWNB;

import weka.classifiers.zh.CAVWNB.RegularizerFactory;

public class RegularizedObjectiveFunctionFactory {
	public WANBObjectiveFunction getObjectiveFunction(String optFunction,String regularizer,int dimensions) {
		return getObjectiveFunction(optFunction, regularizer, dimensions, 1.0);
	}

	public WANBObjectiveFunction getObjectiveFunction(String optFunction, String regularizer, int dimensions,
			double lambda) {
		WANBObjectiveFunction f = new ObjectiveFunctionFactory().getObjectiveFunction(optFunction,dimensions);
		WANBObjectiveFunction r = new RegularizerFactory().getRegularizer(regularizer, dimensions, lambda);
		WANBObjectiveFunction add = new AdditionObjectiveFunction(f,r);
		return add;
	}
}
