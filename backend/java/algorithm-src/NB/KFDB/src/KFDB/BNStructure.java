package KFDB;

import java.io.BufferedReader;
import java.io.File;
import java.io.FileNotFoundException;
import java.io.FileReader;
import java.io.IOException;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.Comparator;
import java.util.List;

import KFDB.wdBayesParametersTree;
//import ESKDB.BNStructure.Pair;
import tools.CorrelationMeasures;
import tools.SUtils;
import weka.core.Instance;
import weka.core.Instances;
import weka.core.Utils;
import weka.core.converters.ArffLoader.ArffReader;

public final class BNStructure {

	int nInstances;
	int nAttributes;
	int nc;
	xxyDist xxyDist_;
	private String m_S = "";
	private int K = 1;
	protected static int MAX_INCORE_N_INSTANCES = 100000;
	private int[] paramsPerAtt;
	private int[][] m_Parents;
	private int[] m_Order;
	public ArrayList<int[]> upperOrder;
	public ArrayList<int[][][]> parentOrder;
	ArrayList<ArrayList<ArrayList<Integer>>> parentOrderforEachAtt;

	public BNStructure(Instances m_Instances, String m_S, int k, int[] ppa) {   
		
		this.m_S = m_S;
		this.K = k;
		
		nInstances = m_Instances.numInstances();
		nAttributes = m_Instances.numAttributes() - 1;   
		nc = m_Instances.numClasses();

		//parent node for each attribute
		m_Parents = new int[nAttributes][];
		m_Order = new int[nAttributes];

		paramsPerAtt = new int[nAttributes];
		for (int u = 0; u < nAttributes; u++) {
			paramsPerAtt[u] = ppa[u];
		}

		parentOrder = new ArrayList<int[][][]>();
		upperOrder = new ArrayList<int[]>();

		for (int i = 0; i < nAttributes; i++) {
			m_Order[i] = i;
		}

		xxyDist_ = new xxyDist(m_Instances);
		if (nInstances > 0) {
			xxyDist_.addToCount(m_Instances);
		}
	}

	public void learnStructure(Instances structure, File sourceFile) throws IOException {

		// First fill xxYDist; everybody needs it
		ArffReader reader = new ArffReader(new BufferedReader(new FileReader(sourceFile)), 10000);
		Instance row;

		while ((row = reader.readInstance(structure)) != null) {
			updateXXYDist(row);
			xxyDist_.setNoData();
			xxyDist_.xyDist_.setNoData();
		}

		switch (m_S) {
		case "KFDB_MSE":
			learnStructureKFDB_MSE_optimize(structure, sourceFile);
			break;
		case "KFDB_ACC":
			learnStructureKFDB_ACC_optimize(structure, sourceFile);
			break;
		default:
			System.out.println("value of m_S has to be in set {KFDB_MSE,KFDB_ACC}");
		}

		// add parent node 
		for (int i = 0; i < parentOrder.size(); i++) {
			for (int j = 0; j < parentOrder.get(i).length; j++) {  

				// add y as its first parent
				int[][] b = parentOrder.get(i)[j];    
				for (int k = 0; k < b.length; k++) {  
					int[] c;
					if (b[k] == null) {       
						c = new int[1];
						c[0] = structure.classIndex();
					} else {
						c = new int[b[k].length + 1];
						c[0] = structure.classIndex();
						for (int z = 0; z < b[k].length; z++) {
							c[z + 1] = b[k][z];    
						}
					}
					parentOrder.get(i)[j][k] = c;
				}
			}
		}
		
		parentOrderforEachAtt = new ArrayList<ArrayList<ArrayList<Integer>>>();
		ArrayList<ArrayList<Integer>> temp = new ArrayList<ArrayList<Integer>>();
		for (int u = 0; u < this.nAttributes; u++) {
			parentOrderforEachAtt.add(temp);
		}

		// combine all the parents for each attribute   
		for (int i = 0; i < upperOrder.size(); i++) {
			int[] order = upperOrder.get(i);
			for (int j = 0; j < parentOrder.get(i).length; j++) {
				temp = (ArrayList<ArrayList<Integer>>) parentOrderforEachAtt.get(order[j]).clone();
				for (int z = 0; z < parentOrder.get(i)[j].length; z++) {
					int[] tempArray = parentOrder.get(i)[j][z];
					if (!isInList(temp, tempArray)) {
						ArrayList<Integer> list = new ArrayList<Integer>();

						for (int k = 0; k < tempArray.length; k++) {
							list.add(tempArray[k]);
						}
						temp.add(list);
					}

				}
				parentOrderforEachAtt.set(order[j], temp);
			}
		}
	}
	

	private void learnStructureKFDB_MSE_optimize(Instances structure, File sourceFile) throws FileNotFoundException, IOException {  
	    
		int m_KDB = K; 
	    
	    // Load the entire data set into memory to avoid repeated disk I/O
	    List<Instance> instances = new ArrayList<>();
	    ArffReader reader = new ArffReader(new BufferedReader(new FileReader(sourceFile)), 10000);
	    Instance instance;
	    while ((instance = reader.readInstance(structure)) != null) {
	        instances.add(instance);
	    }
	    int N = instances.size();  // total number of instances
	    
	    // Compute mutual information (MI) and conditional MI (CMI)
	    double[] mi = new double[nAttributes];
	    double[][] cmi = new double[nAttributes][nAttributes];
	    CorrelationMeasures.getMutualInformation(xxyDist_.xyDist_, mi);
	    CorrelationMeasures.getCondMutualInf(xxyDist_, cmi);
	    m_Order = SUtils.sort(mi);
	    
	    // Learn candidate parent nodes for each attribute
	    for (int u = 0; u < nAttributes; u++) {
	        int nk = Math.min(u, m_KDB);
	        if (nk > 0) {
	            m_Parents[u] = new int[nk];
	            double[] cmi_values = new double[u];
	            for (int j = 0; j < u; j++) {
	                cmi_values[j] = cmi[m_Order[u]][m_Order[j]];
	            }
	            int[] cmiOrder = SUtils.sort(cmi_values);
	            for (int j = 0; j < nk; j++) {
	                m_Parents[u][j] = m_Order[cmiOrder[j]];
	            }
	        }
	    }
	    
	    // Build parameter tree with LOOCV support and update counts
	    wdBayesParametersTree dParameters_ = new wdBayesParametersTree(nAttributes, nc, paramsPerAtt, m_Order, m_Parents, 1);
	    for (Instance inst : instances) { 
	        dParameters_.update(inst);
	    }
	    dParameters_.countsToProbability();
	    
	    double[][] prevBestPosterior = new double[N][nc]; // Store the posterior probability of the optimal k of the previous attribute
	    double[][][] currentPosterior = new double[N][m_KDB + 1][nc]; // Store the posterior probabilities of all K of the current attribute
	    
	    int[] Attparentnum = new int[nAttributes];
	    double[] foldLossFunctallK_ = new double[m_KDB + 1];  
	    double[][] posteriorDist = new double[m_KDB + 1][nc]; 
	    
	    // each attribute
	    for (int m = 0; m < nAttributes; m++) {
	        if (m == 0) {
	            // first attribute
	            int M = 0;
	            Arrays.fill(foldLossFunctallK_, 0);
	            for (Instance inst : instances) { 
	                // clear posteriorDist
	                for (int i = 0; i < posteriorDist.length; i++) {
	                    Arrays.fill(posteriorDist[i], 0);
	                }
	                
	                // prior probability
	                int x_C = (int) inst.classValue();
	                for (int y = 0; y < nc; y++) {
	                    posteriorDist[0][y] = dParameters_.ploocv(y, x_C);     
	                }
	                for (int k = 1; k <= m_KDB; k++) {
	                    System.arraycopy(posteriorDist[0], 0, posteriorDist[k], 0, nc); 
	                }
	                
	                // update posterior probability
	                dParameters_.updateClassDistributionloocv(posteriorDist, 0, m_Order[0], inst, m_KDB);  
	                for (int k = 0; k <= m_KDB; k++) {
	                    System.arraycopy(posteriorDist[k], 0, currentPosterior[M][k], 0, nc);
	                }
	                M++;
	            }
	            Attparentnum[0] = 0;
	            for (int i = 0; i < N; i++) {
	                System.arraycopy(currentPosterior[i][0], 0, prevBestPosterior[i], 0, nc);
	            }
	        } else {
	            // Handling subsequent attributes
	            int A = 0;
	            Arrays.fill(foldLossFunctallK_, 0);
	            for (Instance inst : instances) { 
	                for (int i = 0; i < posteriorDist.length; i++) {
	                    Arrays.fill(posteriorDist[i], 0);
	                }
	                  
	                for (int k = 0; k <= m_KDB; k++) {
	                    System.arraycopy(prevBestPosterior[A], 0, posteriorDist[k], 0, nc);
	                }
	                
	                // Update the posterior probability of the current attribute
	                dParameters_.updateClassDistributionloocv(posteriorDist, m, m_Order[m], inst, m_KDB);  
	                
	                // Save the posterior probability of all k values of the current attribute
	                for (int k = 0; k <= m_KDB; k++) {
	                    System.arraycopy(posteriorDist[k], 0, currentPosterior[A][k], 0, nc);
	                }
	                
	                // Calculate MSE
	                int x_C = (int) inst.classValue();
	                for (int k = 0; k <= m_KDB; k++) {
	                    SUtils.normalize(posteriorDist[k]);
	                    double error = 1.0 - posteriorDist[k][x_C];
	                    foldLossFunctallK_[k] += error * error;
	                }
	                A++;
	            }
	            
	            // Find the k value corresponding to the minimum MSE
	            double globalmin = foldLossFunctallK_[0];
	            Attparentnum[m] = 0;   
	            for (int k = 1; k <= m_KDB; k++) {
	                if (foldLossFunctallK_[k] < globalmin) {
	                    globalmin = foldLossFunctallK_[k];
	                    Attparentnum[m] = k;
	                }
	            }
	            
	            // Update prevBestPosterior to the optimal k value result for the current attribute
	            int currBestK = Attparentnum[m];
	            for (int i = 0; i < N; i++) {
	                System.arraycopy(currentPosterior[i][currBestK], 0, prevBestPosterior[i], 0, nc);
	            }
	        }
	    }
	    
	    // Update parent node
	    int[][] m_ParentsTemp = new int[nAttributes][];
	    for (int u = 0; u < nAttributes; u++) {
	        if (m_Parents[u] != null) {
	            int nK = Attparentnum[u];
	            m_ParentsTemp[u] = (nK == 0) ? null : Arrays.copyOf(m_Parents[u], nK); 
	        }
	    }
	    m_Parents = m_ParentsTemp;
	    
	    upperOrder.add(m_Order);
	    int[][][] tempParent = new int[nAttributes][1][];
	    for (int i = 0; i < nAttributes; i++) {
	        tempParent[i][0] = m_Parents[i];
	    }
	    parentOrder.add(tempParent);
	    
	    m_Order = null;
	    m_Parents = null;
	    tempParent = null;
	}
	
	private void learnStructureKFDB_ACC_optimize(Instances structure, File sourceFile) throws FileNotFoundException, IOException {  //对每个数据集的每个属性都选择合适的父节点个数
		
		int m_KDB = K; 
		
		// Load the entire data set into memory to avoid repeated disk I/O
	    List<Instance> instances = new ArrayList<>();
	    ArffReader reader = new ArffReader(new BufferedReader(new FileReader(sourceFile)), 10000);
	    Instance instance;
	    while ((instance = reader.readInstance(structure)) != null) {
	        instances.add(instance);
	    }
	    int N = instances.size(); // total number of instances
	    
	    // Compute mutual information (MI) and conditional MI (CMI)
	    double[] mi = new double[nAttributes];
	    double[][] cmi = new double[nAttributes][nAttributes];
	    CorrelationMeasures.getMutualInformation(xxyDist_.xyDist_, mi);
	    CorrelationMeasures.getCondMutualInf(xxyDist_, cmi);
	    m_Order = SUtils.sort(mi);
	    
	    // Learn candidate parent nodes for each attribute
	    for (int u = 0; u < nAttributes; u++) {
	        int nk = Math.min(u, m_KDB);
	        if (nk > 0) {
	            m_Parents[u] = new int[nk];
	            double[] cmi_values = new double[u];
	            for (int j = 0; j < u; j++) {
	                cmi_values[j] = cmi[m_Order[u]][m_Order[j]];
	            }
	            int[] cmiOrder = SUtils.sort(cmi_values);
	            for (int j = 0; j < nk; j++) {
	                m_Parents[u][j] = m_Order[cmiOrder[j]];
	            }
	        }
	    }
	    
	    // Build parameter tree with LOOCV support and update counts
	    wdBayesParametersTree dParameters_ = new wdBayesParametersTree(nAttributes, nc, paramsPerAtt, m_Order, m_Parents, 1);
	    for (Instance inst : instances) { 
	        dParameters_.update(inst);
	    }
	    dParameters_.countsToProbability();
	    
	    double[][] prevBestPosterior = new double[N][nc]; // Store the posterior probability of the optimal k of the previous attribute
	    double[][][] currentPosterior = new double[N][m_KDB + 1][nc]; // Store the posterior probabilities of all K of the current attribute
	    
	    int[] Attparentnum = new int[nAttributes];
	    double[] foldLossFunctallK_ = new double[m_KDB + 1];  
	    double[][] posteriorDist = new double[m_KDB + 1][nc]; 
	    
	    double[] correctNum = new double[m_KDB + 1];
	    double[] incorrectNum = new double[m_KDB + 1];
	   
	    // each attribute
	    for (int m = 0; m < nAttributes; m++) {
	        if (m == 0) {
	        	// first attribute
	            int M = 0;
	            Arrays.fill(foldLossFunctallK_, 0);
	            for (Instance inst : instances) {
	                for (int i = 0; i < posteriorDist.length; i++) {
	                    Arrays.fill(posteriorDist[i], 0);
	                }
	                // Calculate prior probability
	                int x_C = (int) inst.classValue();
	                for (int y = 0; y < nc; y++) {
	                    posteriorDist[0][y] = dParameters_.ploocv(y, x_C);     
	                }
	                for (int k = 1; k <= m_KDB; k++) {
	                    System.arraycopy(posteriorDist[0], 0, posteriorDist[k], 0, nc); 
	                }
	                
	                // update posterior probability
	                dParameters_.updateClassDistributionloocv(posteriorDist, 0, m_Order[0], inst, m_KDB);  
	                       
	                for (int k = 0; k <= m_KDB; k++) {
	                    System.arraycopy(posteriorDist[k], 0, currentPosterior[M][k], 0, nc);
	                }
	                M++;
	            }
	            Attparentnum[0] = 0;
	            for (int i = 0; i < N; i++) {
	                System.arraycopy(currentPosterior[i][0], 0, prevBestPosterior[i], 0, nc);
	            }
	        } else {
	        	// Handling subsequent attributes
	            int A = 0;
	            Arrays.fill(foldLossFunctallK_, 0);
	        	Arrays.fill(correctNum, 0);
				Arrays.fill(incorrectNum, 0);	
	            for (Instance inst : instances) {
	                // Reset posteriorDist
	                for (int i = 0; i < posteriorDist.length; i++) {
	                    Arrays.fill(posteriorDist[i], 0);
	                }
                
	                for (int k = 0; k <= m_KDB; k++) {
	                    System.arraycopy(prevBestPosterior[A], 0, posteriorDist[k], 0, nc);
	                }
	                
	                // Update the posterior probability of the current attribute
	                dParameters_.updateClassDistributionloocv(posteriorDist, m, m_Order[m], inst, m_KDB);  
	                
	                // Save the posterior probability of all k values of the current attribute
	                for (int k = 0; k <= m_KDB; k++) {
	                    System.arraycopy(posteriorDist[k], 0, currentPosterior[A][k], 0, nc);
	                }
	                
	                //Calculate ACC
	                int x_C = (int) inst.classValue();
	                for (int k = 0; k <= m_KDB; k++) {
	                    SUtils.normalize(posteriorDist[k]);
	                    int prediectedClass = 0;
						double prediectedProbability = posteriorDist[k][0];
						for(int y = 1; y < nc; y++) {
							if(prediectedProbability < posteriorDist[k][y]) {
								prediectedProbability = posteriorDist[k][y];
								prediectedClass = y;
							}
						}
						
						if(prediectedClass == x_C) {
							correctNum[k]++;
						}else
							incorrectNum[k]++;		
						
	                }
	                A++;
	            }
				 for (int k = 0; k <= m_KDB; k++) {
					 foldLossFunctallK_[k] += correctNum[k]/N;
				 }
	            
	            // Find the k value corresponding to the maximum ACC
				double globalmax = foldLossFunctallK_[0];
	            Attparentnum[m] = 0;     
				for (int k = 1; k <= m_KDB; k++) {
					if (foldLossFunctallK_[k] > globalmax) {
						globalmax = foldLossFunctallK_[k];
						Attparentnum[m] = k;
					}
				}
	            
	            // Update prevBestPosterior to the optimal k value result for the current attribute
	            int currBestK = Attparentnum[m];
	            for (int i = 0; i < N; i++) {
	                System.arraycopy(currentPosterior[i][currBestK], 0, prevBestPosterior[i], 0, nc);
	            }
	        }
	    }
	    
	    // Update parent node
	    int[][] m_ParentsTemp = new int[nAttributes][];
	    for (int u = 0; u < nAttributes; u++) {
	        if (m_Parents[u] != null) {
	            int nK = Attparentnum[u];
	            m_ParentsTemp[u] = (nK == 0) ? null : Arrays.copyOf(m_Parents[u], nK); // 用Arrays.copyOf优化
	        }
	    }
	    m_Parents = m_ParentsTemp;
	    
	    upperOrder.add(m_Order);
	    int[][][] tempParent = new int[nAttributes][1][];
	    for (int i = 0; i < nAttributes; i++) {
	        tempParent[i][0] = m_Parents[i];
	    }
	    parentOrder.add(tempParent);
	    
	    m_Order = null;
	    m_Parents = null;
	    tempParent = null;
	}
	
	private void updateXXYDist(Instance instance) {
		xxyDist_.update(instance);
	}

	public xxyDist get_XXYDist() {
		return xxyDist_;
	}

	public int[] get_Order() {
		return m_Order;
	}

	public int[][] get_Parents() {
		return m_Parents;
	}

	public ArrayList<int[]> getUpperOrder() {
		return this.upperOrder;
	}

	public ArrayList<int[][][]> getLowerOrder() {
		return parentOrder;
	}

	public ArrayList<ArrayList<ArrayList<Integer>>> getParentOrderforEachAtt() {
		return parentOrderforEachAtt;
	}

	public static boolean isInList(ArrayList<ArrayList<Integer>> list, int[] candidate) {

		for (final ArrayList<Integer> item : list) {
			// convert arraylist to int[]
			int[] temp = new int[item.size()];
			for (int i = 0; i < temp.length; i++) {
				temp[i] = item.get(i).intValue();
			}

			if (Arrays.equals(temp, candidate)) {
				return true;
			}
		}
		return false;
	}	

					 		
}


