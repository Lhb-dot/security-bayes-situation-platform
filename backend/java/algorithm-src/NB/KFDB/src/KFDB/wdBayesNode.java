package KFDB;

import tools.SUtils;

public class wdBayesNode {  

	public double[] xyCount;		// Count for x val and the y val
	public double[] xyProbability;		// Count for x val and the y val
	wdBayesNode[] children;	
	public int att;          // the Attribute whose values select the next child
	public int index;
	private int paramsPerAttVal;

	// default constructor - init must be called after construction
	public wdBayesNode() {
		
	}     

	// initialize a new uninitialized node
	public void init(int nc, int paramsPerAttVal) {
		this.paramsPerAttVal = paramsPerAttVal;
		index = -1;
		att = -1;
		xyCount = new double[nc * paramsPerAttVal];
		xyProbability = new double[nc * paramsPerAttVal];
		children = null;
	}  

	// Reset a node to be empty
	public void clear() { 
		att = -1;
		children = null;
	}      

	public void setXYCount(int v, int y, double val) {
		xyCount[y * paramsPerAttVal + v] = val;  
	}

	public double getXYCount(int v, int y) {
		return xyCount[y * paramsPerAttVal + v];		
	}

	public void incrementXYCount(int v, int y) {
		xyCount[y * paramsPerAttVal + v] ++;
	}

	public void decrementXYCount(int v, int y) {
		xyCount[y * paramsPerAttVal + v] --;
	}
	
	public void setXYProbability(int v, int y, double val) {
		xyProbability[y * paramsPerAttVal + v] = val;
	}

	public double getXYProbability(int v, int y) {
		return xyProbability[y * paramsPerAttVal + v];		
	}

	public double updateClassDistribution(int value, int c) {
		double totalCount = getXYCount(0,c);
		for (int v = 1; v < paramsPerAttVal; v++) {
			 totalCount += getXYCount(v,c);
		}
		double prob = 0.0;
		prob = Math.log(SUtils.MEsti(getXYCount(value,c), totalCount, paramsPerAttVal));
		return prob;
	}
}