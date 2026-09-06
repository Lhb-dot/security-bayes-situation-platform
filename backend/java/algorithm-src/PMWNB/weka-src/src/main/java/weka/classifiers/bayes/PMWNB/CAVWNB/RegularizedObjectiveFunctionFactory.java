package weka.classifiers.bayes.PMWNB.CAVWNB;

import weka.classifiers.bayes.PMWNB.CAVWNB.RegularizerFactory;

public class RegularizedObjectiveFunctionFactory {
	public WANBObjectiveFunction getObjectiveFunction(String optFunction, String regularizer, int dimensions) {
		WANBObjectiveFunction f = new ObjectiveFunctionFactory().getObjectiveFunction(optFunction, dimensions);
		WANBObjectiveFunction r = new RegularizerFactory().getRegularizer(regularizer, dimensions);
		WANBObjectiveFunction add = new AdditionObjectiveFunction(f, r);
		return add;
	}
}
