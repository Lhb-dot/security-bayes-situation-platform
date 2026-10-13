/*
 * xyDist.java     
 * Combination of attributes and class labels
 * 
 */

package KFDB;

import tools.SUtils;
import weka.core.Instance;
import weka.core.Instances;

public class xyDist implements java.io.Serializable {

	private int[][] counts_;
	private int[] classCounts_;	

	private double[][] probs_;
	private double[] classProbs_;

	private int N;
	private int n;
	private int nc;

	private int paramsPerAtt[];	

	public xyDist(Instances instances) {

		N = instances.numInstances();
		n = instances.numAttributes() - 1; 
		nc = instances.numClasses();

		// number of attribute values for each attribute
		paramsPerAtt = new int[n];  
		for (int u = 0; u < n; u++) {
			paramsPerAtt[u] = instances.attribute(u).numValues();
		}

		classCounts_ = new int[nc];   
		counts_ = new int[n][];   

		for (int u1 = 0; u1 < n; u1++) {
			counts_[u1] = new int[paramsPerAtt[u1] * nc];
		}	
	}


	public void addToCount(Instances instances) {		
		for (int ii = 0; ii < N; ii++) {
			Instance inst = instances.instance(ii);
			update(inst);
		}
	}

	
	public void update(Instance inst) {
		int x_C = (int) inst.value(inst.numAttributes()-1);
		classCounts_[x_C]++;		

		for (int u1 = 0; u1 < n; u1++) {
			int x_u1 = (int) inst.value(u1);
			int pos = x_u1 * nc + x_C;
			counts_[u1][pos]++;
		}
	}	

	public void countsToProbs() {

		classProbs_ = new double[nc];
		probs_ = new double[n][];

		for (int u1 = 0; u1 < n; u1++) {
			probs_[u1] = new double[paramsPerAtt[u1] * nc];
		}

		for (int c = 0; c < nc; c++) {
			classProbs_[c] = Math.log(SUtils.MEsti(classCounts_[c], N, nc));
		}

		for (int c = 0; c < nc; c++) {
			for (int u = 0; u < n; u++) {				
				for (int uval = 0; uval < paramsPerAtt[u]; uval++) {
					int pos = uval*nc + c;
					probs_[u][pos] = Math.log(Math.max(SUtils.MEsti(counts_[u][pos], classCounts_[c], paramsPerAtt[u]), 1e-75));
				}				
			}
		}

	}
	
	public double[] getClassProbs() {
		return classProbs_;		
	}

	// p(a=v|Y=y) using M-estimate
	public double p(int u1, int u1val, int y) {
		int pos = u1val*nc + y;
		return SUtils.MEsti(counts_[u1][pos], classCounts_[y], paramsPerAtt[u1]);
	}

	public double pp(int u1, int u1val, int y) {
		int pos = u1val*nc + y;
		return probs_[u1][pos];
	}

	// p(Y=y) using M-estimate
	public double p(int y) {
		return SUtils.MEsti(classCounts_[y], N, nc); 
	}

	public double pp(int y) {
		return classProbs_[y]; 
	}

	// p(a=v) using M-estimate
	public double p(int u1, int u1val) {
		return SUtils.MEsti(getCount(u1,u1val), N, paramsPerAtt[u1]);
	}

	// p(a=v, Y=y) using M-estimate
	public double jointP(int u1, int u1val, int y) {
		int pos = u1val*nc + y;
		return SUtils.MEsti(counts_[u1][pos], N, paramsPerAtt[u1] * nc);
	}

	// count[A=v,Y=y]
	public int getCount(int u1, int u1val, int y) {
		int pos = u1val*nc + y;
		return counts_[u1][pos];
	}

	// count[A=v]
	public int getCount(int u1, int u1val) {
		int c = 0;
		for (int y = 0; y < nc; y++) {
			int pos = u1val*nc + y;
			c += counts_[u1][pos];
		}
		return c;
	}

	// count[Y=y]
	public int getClassCount(int y) { return classCounts_[y]; }

	public int getNoClasses() { return nc; }

	public int getNoAtts() { return n; }

	public int getNoCatAtts() { return n; }

	public int getNoData() { return N; }
	
	public void setNoData() { N++; }

	public int getNoValues(int u) { return paramsPerAtt[u]; }

	public void setClassProbs(int c, double d) {
		classProbs_[c] = d;		
	}

}
