package weka.classifiers.zh.CAVWNB;

import weka.classifiers.zh.CAVWNB.WANBDistribution;
import weka.core.Instances;
 
public abstract class BaseObjectiveFunction implements WANBObjectiveFunction {
	protected int n;
	protected WANBDistribution distrib;
	protected Instances instances;
	public BaseObjectiveFunction(int n) {
		this.n = n;
	}

	@Override
	public void init(WANBDistribution distrib, Instances instances2) {
		//System.out.println("BaseObjectiveFunction am initializing");
		this.distrib = distrib;
		this.instances = instances2;
	}
	
	@Override
	public int getNumDimensions() {
	 	return n;
	}
} //ends class 

