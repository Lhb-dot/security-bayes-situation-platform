/*
 * xxyDist.java     
 * Combination of two attributes and class labels
 * 
 */

package KFDB;

import tools.SUtils;
import weka.core.Instance;
import weka.core.Instances;

public class xxyDist implements java.io.Serializable {

	private double[][][] counts_;
	private double[][][] probs_;

	public xyDist xyDist_;

	private int N;
	private int n;
	private int nc;

	private int paramsPerAtt[];

	public xxyDist(Instances instances) {

		N = instances.numInstances();
		n = instances.numAttributes() - 1; // -1 is due to the class presence in numAttributes
		nc = instances.numClasses();

		paramsPerAtt = new int[n];
		for (int u = 0; u < n; u++) {
			paramsPerAtt[u] = instances.attribute(u).numValues();
		}

		xyDist_ = new xyDist(instances);		
		counts_ = new double[n][][];

		for (int u1 = 1; u1 < n; u1++) {         
			counts_[u1] = new double[paramsPerAtt[u1] * u1][];
			for (int u1val = 0; u1val < paramsPerAtt[u1]; u1val++) {
				for (int u2 = 0; u2 < u1; u2++) {
					int pos1 = u1*u1val + u2;
					counts_[u1][pos1] = new double[paramsPerAtt[u2] * nc];
				}
			}
		}
	}

	public void addToCount(Instances instances) {
		for (int ii = 0; ii < N; ii++) {
			Instance inst = instances.instance(ii);
			//xyDist_.update(inst);

			update(inst);
		}
	}

	public void update(Instance inst) {		
		xyDist_.update(inst);

		int x_C = (int) inst.value(inst.numAttributes()-1);

		for (int u1 = 1; u1 < n; u1++) {
			int x_u1 = (int) inst.value(u1);

			for (int u2 = 0; u2 < u1; u2++) {
				int x_u2 = (int) inst.value(u2);

				int pos1 = u1*x_u1 + u2;
				int pos2 = x_u2*nc + x_C; 
				counts_[u1][pos1][pos2]++;
			}
		}
	}

	/* 
	 * TAN uses this function, the function can also be used by A1DE.
	 * However, the functionality in A1DE is not implemented.
	 */	
	public void countsToProbs() {
		xyDist_.countsToProbs();

		probs_ = new double[n][][];

		for (int u1 = 1; u1 < n; u1++) {
			probs_[u1] = new double[paramsPerAtt[u1] * u1][];

			for (int u1val = 0; u1val < paramsPerAtt[u1]; u1val++) {
				for (int u2 = 0; u2 < u1; u2++) {
					int pos1 = u1*u1val + u2;
					probs_[u1][pos1] = new double[2 * (paramsPerAtt[u2] * nc)];  
				}
			}
		}

		
		for (int c = 0; c < nc; c++) {
			for (int u1 = 1; u1 < n; u1++) {
				for (int u1val = 0; u1val < paramsPerAtt[u1]; u1val++) { 

					for (int u2 = 0; u2 < u1; u2++) {
						for (int u2val = 0; u2val < paramsPerAtt[u2]; u2val++) {					

							int pos1 = u1*u1val + u2;
							int pos2 = u2val*nc + c;

							int pos3 = (paramsPerAtt[u2] * nc) + (u2val*nc + c);

							probs_[u1][pos1][pos2] = Math.log(Math.max(SUtils.MEsti(ref(u1,u1val,u2,u2val,c), 
									xyDist_.getCount(u2,u2val,c), 
									paramsPerAtt[u1]), 1e-75));							
							probs_[u1][pos1][pos3] = Math.log(Math.max(SUtils.MEsti(ref(u1,u1val,u2,u2val,c), 
									xyDist_.getCount(u1,u1val,c), 
									paramsPerAtt[u2]), 1e-75));
						}
					}
				}
			}
		}

	}

	/* 
	 * This function is used by AnJE.
	 */	
	public void countsToAJEProbs() {
		xyDist_.countsToProbs();
		
		probs_ = new double[n][][];

		for (int u1 = 1; u1 < n; u1++) {
			probs_[u1] = new double[paramsPerAtt[u1] * u1][];

			for (int u1val = 0; u1val < paramsPerAtt[u1]; u1val++) {
				for (int u2 = 0; u2 < u1; u2++) {
					int pos1 = u1*u1val + u2;
					probs_[u1][pos1] = new double[paramsPerAtt[u2] * nc];
				}
			}
		}
		
		for (int c = 0; c < nc; c++) {
			
			for (int u1 = 1; u1 < n; u1++) {
				for (int u1val = 0; u1val < paramsPerAtt[u1]; u1val++) { 

					for (int u2 = 0; u2 < u1; u2++) {
						for (int u2val = 0; u2val < paramsPerAtt[u2]; u2val++) {					

							int pos1 = u1*u1val + u2;
							int pos2 = u2val*nc + c;							
							
							probs_[u1][pos1][pos2] = Math.max(SUtils.MEsti(ref(u1,u1val,u2,u2val,c), 
									xyDist_.getClassCount(c), 
									paramsPerAtt[u1]*paramsPerAtt[u2]), 1e-75);
						}
					}
				}
			}
		}
		
	}

	// p(x1=v1, x2=v2, Y=y) unsmoothed
	double rawJointP(int x1, int v1, int x2, int v2, int y) {
		return ref(x1,v1,x2,v2,y) / N;
	}

	// p(x1=v1, x2=v2, Y=y) using M-estimate
	public double jointP(int x1, int v1, int x2, int v2, int y) {
		return SUtils.MEsti(ref(x1,v1,x2,v2,y), N,  paramsPerAtt[x1] * paramsPerAtt[x2] * nc); 
	}

	// p(x1=v1, x2=v2) using M-estimate
	public double jointP(int x1, int v1, int x2, int v2) {
		return SUtils.MEsti(getCount(x1,v1,x2,v2), N, paramsPerAtt[x1] * paramsPerAtt[x2]);
	}

	// p(x1=v1|Y=y, x2=v2) using M-estimate
	public double p(int x1, int v1, int x2, int v2, int y) {
		return SUtils.MEsti(ref(x1,v1,x2,v2,y), xyDist_.getCount(x2,v2,y), paramsPerAtt[x1]); 
	}

	// similar to p, but (Conditional) probabilities -- P(x1|y,x2) are already computed
	public double pp(int x1, int v1, int x2, int v2, int y) {
		return pref(x1,v1,x2,v2,y); 
	}
	
	// similar to p, but probabilities -- P(x1,x2|y) are already computed
	// p(x1=v1, x2=v2|Y=y) using M-estimate, probabilities already computed
	public double jp(int x1, int v1, int x2, int v2, int y) {
		return jref(x1,v1,x2,v2,y); 
	}

	// count for instances x1=v1, x2=v2
	public int getCount(int x1, int v1, int x2, int v2) {
		int c = 0;

		for (int y = 0; y < nc; y++) {
			c += ref(x1,v1,x2,v2,y);
		}
		return c;
	}

	// p(x1=v1, x2=v2, Y=y) unsmoothed
	public double getCount(int x1, int v1, int x2, int v2, int y) {
		return ref(x1,v1,x2,v2,y);
	}

	// count_[X1=x1][X2=x2][Y=y]
	private double ref(int x1, int v1, int x2, int v2, int y) {
		if (x2 > x1) {
			int t = x1;
			x1 = x2;
			x2 = t;
			t = v1;
			v1 = v2;
			v2 = t;
		}

		//return &count_[x1][v1*x1+x2][v2*noOfClasses_+y];
		int pos1 = v1*x1 + x2;
		int pos2 = v2*nc + y;
		return counts_[x1][pos1][pos2];
	}

	// probs_[X1=x1][X2=x2][Y=y]
	private double pref(int x1, int v1, int x2, int v2, int y) {

		boolean isX2gX1 = false;
		if (x2 > x1) {
			isX2gX1 = true;
			int t = x1;
			x1 = x2;
			x2 = t;
			t = v1;
			v1 = v2;
			v2 = t;
		}

		int pos1 = v1*x1 + x2;
		int pos2 = isX2gX1 ? (paramsPerAtt[x2] * nc) + (v2*nc + y) : (v2*nc + y);

		return probs_[x1][pos1][pos2];
	}
	
	// probs_[X1=x1][X2=x2][Y=y]
	private double jref(int x1, int v1, int x2, int v2, int y) {
		if (x2 > x1) {
			int t = x1;
			x1 = x2;
			x2 = t;
			t = v1;
			v1 = v2;
			v2 = t;
		}

		//return &count_[x1][v1*x1+x2][v2*noOfClasses_+y];
		int pos1 = v1*x1 + x2;
		int pos2 = v2*nc + y;
		return probs_[x1][pos1][pos2];
	}

	public int getNoAtts() { return n; }

	public int getNoCatAtts() { return n; }

	public int getNoValues(int a) { return paramsPerAtt[a]; }

	public int getNoData() { return N; }
	
	public void setNoData() { N++; }

	public int getNoClasses() { return nc; }

	public int[] getNoValues() { return paramsPerAtt; }

}
