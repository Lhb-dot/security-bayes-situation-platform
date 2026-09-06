package weka.classifiers.bayes.PMWNB.CAVWNB;

import weka.classifiers.bayes.PMWNB.CAVWNB.WANBDistribution;
import weka.core.Instances;

public interface WeightComputer {
	double[] assessWeights(WANBDistribution distrib, Instances instances);
}
