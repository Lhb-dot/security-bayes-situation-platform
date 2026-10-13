package tools;

import KFDB.xxyDist;
import KFDB.xyDist;

public class CorrelationMeasures {

	/**
	 * Find maximum spanning tree
	 * 
	 * @param numNode: Number of node in the graph
	 * @param weight: weight[i][j] = weight[j][i] is the weight of the edge from node i to node j
	 * @exception Exception: if the instance could not be incorporated in the model.
	 */
	public static void findMST(int numNode, double[][] weight, int[] m_Parents) {

		// included in tree? If yes, this value is 1 otherwise is -1
		int[] inTree = new int[numNode];
		// distance[i] is the largest weight of node i to those nodes already in
		// the tree
		double[] distance = new double[numNode];

		for (int i = 0; i < numNode; i++) {
			inTree[i] = -1;
		}
		// Add node 0 to the tree
		inTree[0] = 1;
		// set distances of other nodes
		for (int i = 1; i < numNode; i++) {
			distance[i] = weight[0][i];
			m_Parents[i] = 0;
		}

		for (int treeSize = 1; treeSize < numNode; treeSize++) {
			// Find the node with the largest distance to the tree
			int max = -1;
			for (int i = 0; i < numNode; i++) {
				// consider nodes that are not in the tree
				if (inTree[i] != 1) {
					if ((max == -1) || (distance[max] < distance[i])) {
						max = i;
					}
				}
			}

			// add node max to the tree
			inTree[max] = 1;
			// update distances for nodes that are not in the tree as new node
			// max is added to the tree
			for (int i = 0; i < numNode; i++) {
				if (inTree[i] == 1)
					continue;
				if (distance[i] < weight[max][i]) {
					distance[i] = weight[max][i];
					m_Parents[i] = max;
				}
			}
		}
	}

	/**
	 *             __
	 *             \               P(x,y)
	 *  MI(X,Y)=   /_  P(x,y)log------------    
	 *            x,y             P(x)P(y)
	 *
	 */
	public static void getMutualInformation(xyDist xyDist_, double[] mi) {
		int nc = xyDist_.getNoClasses();
		int n = xyDist_.getNoAtts();
		double N = xyDist_.getNoData();

		int[] paramsPerAtt = new int[n];
		for (int u = 0; u < n; u++) {
			paramsPerAtt[u] = xyDist_.getNoValues(u);		
		}

		for (int u = 0; u < n; u++) {
			double m = 0;
			for (int uval = 0; uval < paramsPerAtt[u]; uval++) {
				for (int y = 0; y < nc; y++) {
					int avyCount = xyDist_.getCount(u, uval, y);
					if (avyCount > 0) {
						m += (avyCount / N) * Math.log( avyCount / ( xyDist_.getCount(u, uval)/N * xyDist_.getClassCount(y) ) ) / Math.log(2);
						//System.out.println(avyCount + ", " + xyDist_.getCount(u, uval) + ", " + xyDist_.getClassCount(y) + " = " + m);
					}
				}
			}
			mi[u] = m;
		}
	}
	
	/**
	 *                 __
	 *                 \                    P(x1,x2|y)
	 * CMI(X1,X2|Y)= = /_   P(x1,x2,y) log-------------    
	 *               x1,x2,y              P(x1|y)P(x2|y)
	 *
	 */
	public static void getCondMutualInf(xxyDist xxyDist_, double[][] cmi) {	

		int nc = xxyDist_.getNoClasses();
		int n = xxyDist_.getNoAtts();
		double N = xxyDist_.getNoData();

		int[] paramsPerAtt = new int[n];
		for (int u = 0; u < n; u++) {
			paramsPerAtt[u] = xxyDist_.getNoValues(u);		
		}

		// Calculate conditional mutual information		
		for (int u1 = 1; u1 < n; u1++) {
			for (int u2 = 0; u2 < u1; u2++) {
				
				double mi = 0;
				for (int u1val = 0; u1val < paramsPerAtt[u1]; u1val++) {					
					for (int u2val = 0; u2val < paramsPerAtt[u2]; u2val++) {
						for (int c = 0; c < nc; c++) {		

							double avvyCount = xxyDist_.getCount(u1, u1val, u2, u2val, c);
							if (avvyCount > 0) {															
								
								double a = avvyCount;
								double b = xxyDist_.xyDist_.getClassCount(c);
								double d = xxyDist_.xyDist_.getCount(u1, u1val, c);
								double e = xxyDist_.xyDist_.getCount(u2, u2val, c);
								
								//System.out.println((a/N) * Math.log((a*b) / (d*e)) / Math.log(2));
								double mitemp = (a/N) * Math.log((a*b) / (d*e)) / Math.log(2);
								mi += mitemp;
							
							}
						}
					}
				}
				cmi[u1][u2] = mi;
				cmi[u2][u1] = mi;
			}
		}		

	}

	/**                        
	 *                __ 
	 *                \                   P(c,x1,x2)p(x1) 
	 *CMI(C;X2|X1)= = /_   P(c,x1,x2) log----------------
	 *               x1,x2,y              P(c,x1)P(x2,x1)
	 *
	 */
	public static void getcondMutualInfForKDBForest(xxyDist xxyDist_, double[][] cmiKDBF) {
		// TODO Auto-generated method stub
		int nc = xxyDist_.getNoClasses();
		int na = xxyDist_.getNoAtts();
		double N = xxyDist_.getNoData();

		int[] paramsPerAtt = new int[na];
		for (int u = 0; u < na; u++) {
			paramsPerAtt[u] = xxyDist_.getNoValues(u);
		}

		for (int u1 = 1; u1 < na; u1++) {
			for (int u2 = 0; u2 < u1; u2++) {
				double mi = 0;
				double mi2 = 0;
				for (int u1val = 0; u1val < paramsPerAtt[u1]; u1val++) {
					for (int u2val = 0; u2val < paramsPerAtt[u2]; u2val++) {
						for (int c = 0; c < nc; c++) {

							double avvyCount = xxyDist_.getCount(u1, u1val, u2, u2val, c); // p(C,x1,x2)
							if (avvyCount > 0) {
								double a = avvyCount;
								double b = xxyDist_.xyDist_.getCount(u1, u1val);// p(x1)
								double d = xxyDist_.xyDist_.getCount(u1, u1val, c);// p(c,x1)
								double e = xxyDist_.getCount(u1, u1val, u2, u2val);// p(x2,x1)

								double mitemp = (a / N) * Math.log((a * b) / (d * e)) / Math.log(2);
								mi += mitemp;

								double f = xxyDist_.xyDist_.getCount(u2, u2val);// p(x2)
								double g = xxyDist_.xyDist_.getCount(u2, u2val, c);// p(c,x2)
								double h = xxyDist_.getCount(u1, u1val, u2, u2val);// p(x1,x2)
								double mitemp2 = (a / N) * Math.log((a * f) / (g * h)) / Math.log(2);
								mi2 += mitemp2;
							}
						}
					}
				}
				cmiKDBF[u1][u2] = mi;
				cmiKDBF[u2][u1] = mi2;
			}
		}
	}
}
