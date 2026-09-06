/**
 *    RODE.java
 *    Copyright 2008 Liangxiao Jiang
 **/

package weka.classifiers.zh.A2WNB;

import weka.classifiers.*;
import weka.core.*;
import weka.classifiers.evaluation.EvaluationUtils;

/**
 * Class for RODE.
 */
public class RODE extends AbstractClassifier{

  /** Number of RODANB. */
  private int m_numRODANB;

  /** define a classifier of RNB */
  private RODANB[] m_RODANB;

  /** The weights of each RODANB. */
  private double[] m_Weights;

  /** The number of setting learning task. */
  private int m_Task=1;
  
  

  public int getM_numRODANB() {
	return m_numRODANB;
}
  
  /** The number of each class value occurs in the dataset */
  private double [] m_ClassCounts;

  /** The number of each attribute value occurs in the dataset */
  private double [] m_AttCounts;

  /** The number of two attributes values occurs in the dataset */
  private double [][] m_AttAttCounts;

  /** The number of class and two attributes values occurs in the dataset */
  private double [][][] m_ClassAttAttCounts;

  /** The number of values for each attribute in the dataset */
  private int [] m_NumAttValues;

  /** The number of values for all attributes in the dataset */
  private int m_TotalAttValues;

  /** The number of classes in the dataset */
  private int m_NumClasses;

  /** The number of attributes including class in the dataset */
  private int m_NumAttributes;

  /** The number of instances in the dataset */
  private int m_NumInstances;

  /** The index of the class attribute in the dataset */
  private int m_ClassIndex;

  /** The starting index of each attribute in the dataset */
  private int [] m_StartAttIndex;

  /** The 2D array of conditional mutual information of each pair attributes */
  private double[][] m_condiMutualInfo;

  /** The average conditional mutual information of all pairs attributes. */
  private double m_average;



/**
   * Builds a classifier for a set of instances.
   *
   * @param instances the instances to train the classifier with
   * @exception Exception if something goes wrong
   */
  public void buildClassifier(Instances data) throws Exception {
	  
	  m_NumClasses = data.numClasses();
      m_ClassIndex = data.classIndex();
      m_NumAttributes = data.numAttributes();
      m_NumInstances = data.numInstances();
      m_TotalAttValues = 0;

      // allocate space for attribute reference arrays
      m_StartAttIndex = new int[m_NumAttributes];
      m_NumAttValues = new int[m_NumAttributes];

      // set the starting index of each attribute and the number of values for
      // each attribute and the total number of values for all attributes (not including class).
      for(int i = 0; i < m_NumAttributes; i++) {
        if(i != m_ClassIndex) {
          m_StartAttIndex[i] = m_TotalAttValues;
          m_NumAttValues[i] = data.attribute(i).numValues();
          m_TotalAttValues += m_NumAttValues[i];
        }
        else {
          m_StartAttIndex[i] = -1;
          m_NumAttValues[i] = m_NumClasses;
        }
      }

      // allocate space for counts and frequencies
      m_ClassCounts = new double[m_NumClasses];
      m_AttCounts = new double[m_TotalAttValues];
      m_AttAttCounts = new double[m_TotalAttValues][m_TotalAttValues];
      m_ClassAttAttCounts = new double[m_NumClasses][m_TotalAttValues][m_TotalAttValues];

      // Calculate the counts
      for(int k = 0; k < m_NumInstances; k++) {
        int classVal=(int)data.instance(k).classValue();
        m_ClassCounts[classVal] ++;
        int[] attIndex = new int[m_NumAttributes];
        for(int i = 0; i < m_NumAttributes; i++) {
          if(i == m_ClassIndex){
            attIndex[i] = -1;
          }
          else{
            attIndex[i] = m_StartAttIndex[i] + (int)data.instance(k).value(i);
            m_AttCounts[attIndex[i]]++;
          }
        }
        for(int Att1 = 0; Att1 < m_NumAttributes; Att1++) {
          if(attIndex[Att1] == -1) continue;
          for(int Att2 = 0; Att2 < m_NumAttributes; Att2++) {
            if((attIndex[Att2] != -1)) {
              m_AttAttCounts[attIndex[Att1]][attIndex[Att2]] ++;
              m_ClassAttAttCounts[classVal][attIndex[Att1]][attIndex[Att2]] ++;
            }
          }
        }
      }

      //compute conditional mutual information of each pair attributes (not including class)
      m_condiMutualInfo=new double[m_NumAttributes][m_NumAttributes];
      m_average=0;
      int number=0;
      for(int son=0;son<m_NumAttributes;son++){
        if(son == m_ClassIndex) continue;
        for(int parent=0;parent<m_NumAttributes;parent++){
          if(parent == m_ClassIndex||parent==son) continue;
          m_condiMutualInfo[son][parent]=conditionalMutualInfo(son,parent);
          m_average+=m_condiMutualInfo[son][parent];
          number++;
        }
      }
      m_average/=number;

	  m_numRODANB=data.numAttributes()-1;
	  m_Weights = new double[m_numRODANB];
	  m_RODANB = new RODANB[m_numRODANB];
	  EvaluationUtils evaluation=new EvaluationUtils();
	  for(int i=0; i<m_numRODANB; i++){
		  //if(i == data.classIndex()) continue;
		  m_RODANB[i] = new RODANB();
		  m_RODANB[i].buildClassifier(data);
		  if(m_Task==1){
			  m_Weights[i]=1;
		  }
		  else if(m_Task==2){
			//  m_Weights[i]=evaluation.getClassifierACC(m_RODANB[i],data);
		  }
		  else if(m_Task==3){
			  //m_Weights[i]=evaluation.getClassifierCLL(m_RODANB[i],data);
		  }
		  else if(m_Task==4){
			  //m_Weights[i]=evaluation.getClassifierAUC(m_RODANB[i],data);
		  }
		  else {
			  throw new Exception ("The input task is error");
		  }
	  }
	  Utils.normalize(m_Weights);
  }
  
  /**
   * Computes conditional mutual information between a pair of attributes.
   *
   * @param son and parent are a pair of attributes
   * @return the conditional mutual information between son and parent given class
   */
  private double conditionalMutualInfo(int son, int parent)throws Exception{

    double CondiMutualInfo=0;
    int sIndex=m_StartAttIndex[son];
    int pIndex=m_StartAttIndex[parent];
    double[] PriorsClass = new double[m_NumClasses];
    double[][] PriorsClassSon=new double[m_NumClasses][m_NumAttValues[son]];
    double[][] PriorsClassParent=new double[m_NumClasses][m_NumAttValues[parent]];
    double[][][] PriorsClassParentSon=new double[m_NumClasses][m_NumAttValues[parent]][m_NumAttValues[son]];

    for(int i=0;i<m_NumClasses;i++){
      PriorsClass[i]=m_ClassCounts[i]/m_NumInstances;
    }

    for(int i=0;i<m_NumClasses;i++){
      for(int j=0;j<m_NumAttValues[son];j++){
        PriorsClassSon[i][j]=m_ClassAttAttCounts[i][sIndex+j][sIndex+j]/m_NumInstances;
      }
    }

    for(int i=0;i<m_NumClasses;i++){
      for(int j=0;j<m_NumAttValues[parent];j++){
        PriorsClassParent[i][j]=m_ClassAttAttCounts[i][pIndex+j][pIndex+j]/m_NumInstances;
      }
    }

    for(int i=0;i<m_NumClasses;i++){
      for(int j=0;j<m_NumAttValues[parent];j++){
        for(int k=0;k<m_NumAttValues[son];k++){
          PriorsClassParentSon[i][j][k]=m_ClassAttAttCounts[i][pIndex+j][sIndex+k]/m_NumInstances;
        }
      }
    }

    for(int i=0;i<m_NumClasses;i++){
      for(int j=0;j<m_NumAttValues[parent];j++){
        for(int k=0;k<m_NumAttValues[son];k++){
          CondiMutualInfo+=PriorsClassParentSon[i][j][k]*log2(PriorsClassParentSon[i][j][k]*PriorsClass[i],PriorsClassParent[i][j]*PriorsClassSon[i][k]);
        }
      }
    }
    return CondiMutualInfo;
  }

  public void setTask(int n) throws Exception {
    m_Task = n;
  }

  public int getTask() {
    return m_Task;
  }

  public void setOptions (String[] options) throws Exception {
    String optionString = Utils.getOption('T', options);
    if (optionString.length() != 0) {
      setTask(Integer.parseInt(optionString));
    }
  }

  public String[] getOptions () {
    String[] options = new String[2];
    int current = 0;
    options[current++] = "-T";
    options[current++] = "" + getTask();
    while (current < options.length) {
      options[current++] = "";
    }
    return  options;
  }

  /**
   * Returns the class probability distribution for an instance.
   *
   * @param instance the instance to be classified
   * @return the distribution the forest generates for the instance
   */
  public double[] distributionForInstance(Instance instance) throws Exception {

    int numClass=instance.numClasses();
    double[] probs = new double[numClass];
    for (int i=0; i<m_numRODANB; i++) {
      if(i == instance.classIndex()) continue;
      double[] dist=m_RODANB[i].distributionForInstance(instance);
      for (int j=0; j<numClass; j++) {
        probs[j]+=m_Weights[i]*dist[j];
      }
    }
    return probs;
  }
  
  /**
   * Returns the class probability distribution for an instance.
   *
   * @param instance the instance to be classified
   * @return the distribution the forest generates for the instance
   */
	public String distributionForInstance1(Instance instance) throws Exception {

		int numClass = instance.numClasses();
		String str = "";
		for (int i = 0; i < m_numRODANB; i++) {
			double[] dist = m_RODANB[i].distributionForInstance(instance);
			int[] onehot = new int[numClass];
			int maxIndex = Utils.maxIndex(dist);
			onehot[maxIndex] = 1;
			for (int s = 0; s < numClass; s++) {
				str += String.valueOf(onehot[s] + ",");
			}
		}
		return str;
	}
  
	public String distributionForInstance2(Instance instance) throws Exception {

		String str = "";
		for (int i = 0; i < m_numRODANB; i++) {
			double[] dist = m_RODANB[i].distributionForInstance(instance);
			int maxIndex = Utils.maxIndex(dist);
			str += String.valueOf(maxIndex + ",");
		}
		return str;

	}
	
	/**
	   * Returns the class probability distribution for an instance.
	   *
	   * @param instance the instance to be classified
	   * @return the distribution the forest generates for the instance
	   */
		public String distributionForInstance3(Instance instance) throws Exception {

			int numClass = instance.numClasses();
			String str = "";
			for (int i = 0; i < m_numRODANB; i++) {
				double[] dist = m_RODANB[i].distributionForInstance(instance);
				for (int s = 0; s < numClass; s++) {
					str += String.valueOf(dist[s] + ",");
				}
			}
			return str;
		}
	
	/**
     * compute the logarithm whose base is 2.
     *
     * @param args x,y are numerator and denominator of the fraction.
     * @return the natual logarithm of this fraction.
     */
    private double log2(double x,double y){

      if(x<1e-6||y<1e-6)
        return 0.0;
      else
        return Math.log(x/y)/Math.log(2);
    }
  
  

  /**
   * Main method for this class.
   *
   * @param argv the options
   */
  public static void main(String[] argv) {

    try {
      System.out.println(Evaluation.evaluateModel(new RODE(), argv));
    } catch (Exception e) {
      e.printStackTrace();
      System.err.println(e.getMessage());
    }
  }

  /**
   * Implement the RODANB classifier.
   */
  private class RODANB extends AbstractClassifier {

	  /** The array to keep track of which attribute has which parent. */
	  private int [] m_Parents;
    
    

    /**
     * Generates the classifier.
     *
     * @param instances set of instances serving as training data
     * @exception Exception if the classifier has not been generated successfully
     */
    public void buildClassifier(Instances instances) throws Exception {

      // reset variable
      

      //Build the max edge.
      searchMaxEdge();
    }

    

    

    /**
     * Build the max edge.
     */
    private void searchMaxEdge() throws Exception {

      m_Parents = new int [m_NumAttributes];
      int temp;
      int m_KValue=(int)Utils.log2(m_NumAttributes-1);
      for (int att1 = 0; att1 < m_NumAttributes; att1++) {
        if(att1 == m_ClassIndex) {
          m_Parents[att1] = -1;
          continue;
        }
        double[] selectValues=new double[m_NumAttributes];
        for (int att2 = 0; att2 < m_NumAttributes; att2++) {
          if (att2 == m_ClassIndex|| att2 == att1) continue;
          selectValues[att2]=m_condiMutualInfo[att1][att2];
        }
        int[] topKindex=new int[m_KValue];
        for(int i=0;i<m_KValue;i++){
          topKindex[i]=Utils.maxIndex(selectValues);
          selectValues[topKindex[i]]=0;
        }
        long number=Math.round((m_KValue-1)*Math.random());
        temp=topKindex[(int)number];
        if(m_condiMutualInfo[att1][temp]>=m_average) m_Parents[att1]=temp;
        else m_Parents[att1] = -1;
      }

    }

    /**
     * Calculates the class membership probabilities for the given test instance.
     *
     * @param instance the instance to be classified
     * @return predicted class probability distribution
     * @exception Exception if there is a problem generating the prediction
     */
    public double [] distributionForInstance(Instance instance) throws Exception {

      //Definition of local variables
      double [] probs = new double[m_NumClasses];
      int sIndex;
      int pIndex;
      double prob;

      // store instance's att values in an int array
      int[] attIndex = new int[m_NumAttributes];
      for(int att = 0; att < m_NumAttributes; att++) {
        if(att == m_ClassIndex)
          attIndex[att] = -1;
        else
          attIndex[att] = m_StartAttIndex[att] + (int)instance.value(att);
      }

      // calculate probabilities for each possible class value
      for(int classVal = 0; classVal < m_NumClasses; classVal++) {
         probs[classVal]=(m_ClassCounts[classVal]+1.0)/(m_NumInstances+m_NumClasses);
         for(int son = 0; son < m_NumAttributes; son++) {
            if(attIndex[son]==-1) continue;
            sIndex=attIndex[son];
            if(m_Parents[son]!=-1){
             pIndex=attIndex[m_Parents[son]];
             prob=(m_ClassAttAttCounts[classVal][pIndex][sIndex]+1.0)/(m_ClassAttAttCounts[classVal][pIndex][pIndex] + m_NumAttValues[son]);
             probs[classVal] *= prob;
            }
            else{
             prob=(m_ClassAttAttCounts[classVal][sIndex][sIndex]+1.0)/(m_ClassCounts[classVal] + m_NumAttValues[son]);
             probs[classVal]*= prob;
            }
         }
      }

      Utils.normalize(probs);
      return probs;
    }
  }
  // End RODANB
}
