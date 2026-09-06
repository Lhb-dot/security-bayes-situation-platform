package weka.classifiers.zh.CAVWNB;

import weka.classifiers.zh.CAVWNB.WANBDistribution;
import weka.core.Instances;

public interface WANBObjectiveFunction extends ObjectiveFunction {
	public void init(WANBDistribution distrib,Instances instances);

	public int getNumDimensions();

}
