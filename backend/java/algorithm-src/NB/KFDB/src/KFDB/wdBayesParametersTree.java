package KFDB;

import tools.SUtils;
import weka.core.Instance;
import weka.core.Instances;

public class wdBayesParametersTree {

	private wdBayesNode[] wdBayesNode_;

	private int N;
	private int n;   
	private int nc;

	private int[] m_ParamsPerAtt;

	private int[] order;    
	private int[][] parents;

	private double[] classCounts;
	private double[] classProbabilities;

	/**
	 * Constructor called by wdBayes
	 */
	public wdBayesParametersTree(int nn, int nc, int[] paramsPerAtt, int[] m_Order, int[][] m_Parents, int m_P) {
		this.n = m_Order.length;   
		this.nc = nc;

		m_ParamsPerAtt = new int[nn];
		for (int u = 0; u < nn; u++) {
			m_ParamsPerAtt[u] = paramsPerAtt[u];
		}

		order = new int[n];
		parents = new int[n][];

		for (int u = 0; u < n; u++) {
			order[u] = m_Order[u];
		}

		for (int u = 0; u < n; u++) {
			if (m_Parents[u] != null) {
				parents[u] = new int[m_Parents[u].length];
				for (int p = 0; p < m_Parents[u].length; p++) {
					parents[u][p] = m_Parents[u][p];
				}
			}
		}

		wdBayesNode_ = new wdBayesNode[n];   
		for (int u = 0; u < n; u++) {
			wdBayesNode_[u] = new wdBayesNode();
			wdBayesNode_[u].init(nc, paramsPerAtt[m_Order[u]]);  
		}

		classCounts = new double[nc];
		classProbabilities = new double[nc];
	}

	/* 
	 * -----------------------------------------------------------------------------------------
	 * Update count statistics that is:  relevant ***xyCount*** in every node
	 * -----------------------------------------------------------------------------------------
	 */

	public void unUpdate(Instance instance) {
		classCounts[(int) instance.classValue()]--;   

		for (int u = 0; u < n; u++) {
			unUpdateAttributeTrie(instance, u, order[u], parents[u]);
		}

		N--;
	}

	public void unUpdateAttributeTrie(Instance instance, int i, int u, int[] lparents) {

		int x_C = (int) instance.classValue();
		int x_u = (int) instance.value(u);		

		wdBayesNode_[i].decrementXYCount(x_u, x_C);	

		if (lparents != null) {

			wdBayesNode currentdtNode_ = wdBayesNode_[i];

			for (int d = 0; d < lparents.length; d++) {
				int p = lparents[d];				

				int x_up = (int) instance.value(p);   
				currentdtNode_.children[x_up].decrementXYCount(x_u, x_C);
				currentdtNode_ = currentdtNode_.children[x_up];
			}
		}
	}

	public void update(Instance instance) {
		
		if(classCounts == null){
			classCounts = new double[nc];
		}
		
		int x_C = (int) instance.value(instance.numAttributes()-1);
		classCounts[x_C]++;

		for (int u = 0; u < this.order.length; u++) {    
			updateAttributeTrie(instance, u, order[u], parents[u]);
		}

		N++;
	}

	public void updateAttributeTrie(Instance instance, int i, int u, int[] lparents) {

		int x_C = (int) instance.value(instance.numAttributes()-1);
		int x_u = (int) instance.value(u);		

		wdBayesNode_[i].incrementXYCount(x_u, x_C);	

		if (lparents != null) {

			wdBayesNode currentdtNode_ = wdBayesNode_[i];

			for (int d = 0; d < lparents.length; d++) {
				int p = lparents[d];  

				if (currentdtNode_.att == -1 || currentdtNode_.children == null) {  
					currentdtNode_.children = new wdBayesNode[m_ParamsPerAtt[p]];
					currentdtNode_.att = p;	
				}

				int x_up = (int) instance.value(p);
				currentdtNode_.att = p;

				// the child has not yet been allocated, so allocate it
				if (currentdtNode_.children[x_up] == null) {
					currentdtNode_.children[x_up] = new wdBayesNode();
					currentdtNode_.children[x_up].init(nc, m_ParamsPerAtt[u]);
				} 

				currentdtNode_.children[x_up].incrementXYCount(x_u, x_C);
				currentdtNode_ = currentdtNode_.children[x_up];
			}
		}
	}

	/* 
	 * -----------------------------------------------------------------------------------------
	 * Convert count into (NB) probabilities
	 * -----------------------------------------------------------------------------------------
	 */

	public void countsToProbability() {
		for (int c = 0; c < nc; c++) {
			classProbabilities[c] = Math.log(Math.max(SUtils.MEsti(classCounts[c], N, nc),1e-75));
		}
		for (int u = 0; u < n; u++) {
			convertCountToProbs(order[u], parents[u], wdBayesNode_[u]);
		}
	}
	
	public void convertCountToProbs(int u, int[] lparents, wdBayesNode pt) {
		//convertCountToProbs(u, lparents, next);
		int att = pt.att;

		if (att == -1) {     
			for (int y = 0; y < nc; y++) {

				int denom = 0;
				for (int dval = 0; dval < m_ParamsPerAtt[u]; dval++) {
					denom += pt.getXYCount(dval, y);
				}

				for (int uval = 0; uval < m_ParamsPerAtt[u]; uval++) {
					double prob = Math.log(Math.max(SUtils.MEsti(pt.getXYCount(uval, y), denom, m_ParamsPerAtt[u]),1e-75));
					if(Double.isNaN(prob)){
						System.err.println(pt.getXYCount(uval, y)+" mest="+SUtils.MEsti(pt.getXYCount(uval, y), denom, m_ParamsPerAtt[u]));
					}
					pt.setXYProbability(uval, y, prob);
				}
			}			
			return;
		}

		while (att != -1) {  
			for (int y = 0; y < nc; y++) {

				int denom = 0;
				for (int dval = 0; dval < m_ParamsPerAtt[u]; dval++) {
					denom += pt.getXYCount(dval, y);
				}

				for (int uval = 0; uval < m_ParamsPerAtt[u]; uval++) {
					double prob = Math.log(Math.max(SUtils.MEsti(pt.getXYCount(uval, y), denom, m_ParamsPerAtt[u]),1e-75));
					pt.setXYProbability(uval, y, prob);
				}
			}

			int numChildren = pt.children.length;
			for (int c = 0; c < numChildren; c++) {
				wdBayesNode next = pt.children[c];
				if (next != null) 					
					convertCountToProbs(u, lparents, next);

				// Flag end of nodes
				att = -1;				
			}			
		}

		return;
	}

	//probability when using leave one out cross validation, the t value is discounted
	public double ploocv(int y, int x_C) {
		if (y == x_C)
			return SUtils.MEsti(classCounts[y] - 1, N - 1, nc);   
		else
			return SUtils.MEsti(classCounts[y], N - 1, nc);
	}

	public void updateClassDistributionloocv(double[][] classDist, int i, int u, Instance instance, int m_KDB) {

		int x_C = (int) instance.value(instance.numAttributes()-1);
		int uval = (int) instance.value(u);  

		wdBayesNode pt = wdBayesNode_[i];
		int att = pt.att;

		// find the appropriate leaf   
		int depth = 0;
		while ( (att != -1)) { //We want to consider kdb k=k 

			// sum over all values of the Attribute for the class to obtain count[y, parents]
			for (int y = 0; y < nc; y++) {
				int totalCount = (int) pt.getXYCount(0, y);   
				for (int val = 1; val < m_ParamsPerAtt[u]; val++) {
					totalCount += pt.getXYCount(val, y);
				}    

				if (y != x_C)
					classDist[depth][y] *= SUtils.MEsti(pt.getXYCount(uval, y), totalCount, m_ParamsPerAtt[u]);
				else
					classDist[depth][y] *= SUtils.MEsti(pt.getXYCount(uval, y)-1, totalCount-1, m_ParamsPerAtt[u]);
			}

			int v = (int) instance.value(att);
			wdBayesNode next = pt.children[v];
			
			// the child has not yet been allocated
			if (next == null) {
				for (int k = depth + 1; k <= m_KDB; k++) {
					for (int y = 0; y < nc; y++) 
						classDist[k][y] = classDist[depth][y];
				}
				return;
			};

			// check that the next node has enough examples for this value;  
			int cnt = 0;
			for (int y = 0; y < nc; y++) {
				cnt += next.getXYCount(uval, y);
			}
			
			//In loocv, we consider minCount=1(+1), since we have to leave out i.
			if (cnt < 2) { 
				depth++;
				// sum over all values of the Attribute for the class to obtain count[y, parents]
				for (int y = 0; y < nc; y++) {
					int totalCount = (int) pt.getXYCount(0, y);
					for (int val = 1; val < m_ParamsPerAtt[u]; val++) {
						totalCount += pt.getXYCount(val, y);
					}    

					if (y != x_C)
						classDist[depth][y] *= SUtils.MEsti(pt.getXYCount(uval, y), totalCount, m_ParamsPerAtt[u]);
					else
						classDist[depth][y] *= SUtils.MEsti(pt.getXYCount(uval, y)-1, totalCount-1, m_ParamsPerAtt[u]);
				}

				for (int k = depth + 1; k <= m_KDB; k++){
					for (int y = 0; y < nc; y++) 
						classDist[k][y] = classDist[depth][y];
				}
				return;
			}

			pt = next;
			att = pt.att; 
			depth++;
		}

		// sum over all values of the Attribute for the class to obtain count[y, parents]  
		for (int y = 0; y < nc; y++) {
			int totalCount = (int) pt.getXYCount(0, y);   
			for (int val = 1; val < m_ParamsPerAtt[u]; val++) {
				totalCount += pt.getXYCount(val, y);
			}    
			if (y != x_C)
				classDist[depth][y] *= SUtils.MEsti(pt.getXYCount(uval, y), totalCount, m_ParamsPerAtt[u]);
			else
				classDist[depth][y] *= SUtils.MEsti(pt.getXYCount(uval, y)-1, totalCount-1, m_ParamsPerAtt[u]);
		}

		for (int k = depth + 1; k <= m_KDB; k++){    
			for (int y = 0; y < nc; y++) 
				classDist[k][y] = classDist[depth][y];
		}

	}
	
	public wdBayesNode getBayesNode(Instance instance, int i, int u, int[] m_Parents) {	

		wdBayesNode pt = wdBayesNode_[i];
		int att = pt.att;

		// find the appropriate leaf
		while (att != -1) {
			int v = (int) instance.value(att);
			wdBayesNode next = pt.children[v];
			if (next == null) 
				break;    
			pt = next;
			att = pt.att;
		}

		return pt;		
	}

	public wdBayesNode getBayesNode(Instance instance, int i) {	

		wdBayesNode pt = wdBayesNode_[i];
		int att = pt.att;

		// find the appropriate leaf
		while (att != -1) {
			int v = (int) instance.value(att);
			wdBayesNode next = pt.children[v];
			if (next == null) 
				break;
			pt = next;
			att = pt.att;
		}

		return pt;		
	}

	public wdBayesNode getBayesNode(Instance instance, int i, int k) {	

		wdBayesNode pt = wdBayesNode_[i];
		int att = pt.att;
		int level = 0;

		if (k == 0) {
			return pt;
		}

		// find the appropriate leaf
		while (att != -1 && level < k) {
			int v = (int) instance.value(att);
			wdBayesNode next = pt.children[v];
			if (next == null) 
				break;
			pt = next;
			att = pt.att;
			level++;
		}

		return pt;		
	}

	public int getNAttributes() {
		return n;
	}

	public double getNLL_MAP(Instances instances) {

		double nll = 0;
		int N = instances.numInstances();
		double mLogNC = -Math.log(nc); 
		double[] myProbs = new double[nc];

		for (int i = 0; i < N; i++) {
			Instance instance = instances.instance(i);

			int x_C = (int) instance.classValue();

			// unboxed logDistributionForInstance_d(instance,nodes);
			for (int c = 0; c < nc; c++) {
				myProbs[c] = classProbabilities[c];
				//myProbs[c] = xyDist.pp(c);
			}
			for (int u = 0; u < n; u++) {
				wdBayesNode bNode = getBayesNode(instance, u);
				for (int c = 0; c < nc; c++) {
					myProbs[c] += bNode.getXYProbability((int) instance.value(order[u]), c);
				}
			}
			SUtils.normalizeInLogDomain(myProbs);
			nll += (mLogNC - myProbs[x_C]);
		}

		return nll;
	}

	public double[] getClassCounts() {
		return classCounts;
	}

	public double[] getClassProbabilities() {
		return classProbabilities;
	}
}