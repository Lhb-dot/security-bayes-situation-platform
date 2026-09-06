package weka.classifiers.bayes.PMWNB.CAVWNB;

import weka.classifiers.bayes.PMWNB.CAVWNB.WANBObjectiveFunction;

public class RegularizerFactory {
	public WANBObjectiveFunction getRegularizer(String regularizer, int dimensions) {
		if (regularizer.compareTo("None") == 0) {
			return new EmptyRegularizer(dimensions);
		} else if (regularizer.compareTo("L2") == 0) {
			return new L2Regularizer(dimensions);
		} else {
			throw new NullPointerException();
		}
	}

}
