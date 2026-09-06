package weka.classifiers.bayes.PMWNB.CAVWNB;

public class ObjectiveFunctionFactory {

	public WANBObjectiveFunction getObjectiveFunction(String name, int dimensions) {
		if (name.compareTo("MSE") == 0) {
			return new MSEObjectiveFunction(dimensions);
		} else if (name.compareTo("CLL") == 0) {
			return new MASPObjectiveFunction(dimensions);
		} else {
			throw new NullPointerException();
		}
	}

}
