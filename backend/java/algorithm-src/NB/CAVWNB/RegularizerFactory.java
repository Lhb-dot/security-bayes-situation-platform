package weka.classifiers.zh.CAVWNB;

import weka.classifiers.zh.CAVWNB.WANBObjectiveFunction;

public class RegularizerFactory {
	public WANBObjectiveFunction getRegularizer(String regularizer,int dimensions) {
		return getRegularizer(regularizer, dimensions, 1.0);
	}

	public WANBObjectiveFunction getRegularizer(String regularizer, int dimensions, double lambda) {
		if (regularizer.compareTo("None") == 0) {
			return new EmptyRegularizer(dimensions);
		} else if (regularizer.compareTo("L2") == 0) {
			return new L2Regularizer(dimensions, lambda);
		} else {
			throw new NullPointerException();
		}
	}

}
