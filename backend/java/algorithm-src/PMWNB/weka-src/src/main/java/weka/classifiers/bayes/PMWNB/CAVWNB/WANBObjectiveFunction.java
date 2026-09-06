package weka.classifiers.bayes.PMWNB.CAVWNB;

import weka.classifiers.bayes.PMWNB.CAVWNB.WANBDistribution;
import weka.core.Instances;

public interface WANBObjectiveFunction extends ObjectiveFunction {
	public void init(WANBDistribution distrib, Instances instances);

	public int getNumDimensions();

}
