package weka.classifiers.zh.CAVWNB;

import weka.classifiers.zh.CAVWNB.WANBDistribution;
import weka.core.Instances;

public interface WeightComputer {
	double[] assessWeights(WANBDistribution distrib, Instances instances);
}
