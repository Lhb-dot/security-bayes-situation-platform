package weka.classifiers.mkx.DIWNB;
 
import weka.core.*;

import java.util.Arrays;
import weka.classifiers.*;
 
/**
 * Implement the IWNB_L classifier.
 */
public class IWNB extends AbstractClassifier {
 
  private static final long serialVersionUID = 1L;
  
 //ÿ�����Ժ��ж�������ֵ
  private int [] AttValuesCounts;
  
 //���Բ������±�
  private int []  AttributeIndex;
  
  //�洢ѵ������
  private Instances m_Instances;
  
 //���е�����ֵ  ������labelֵ  
  private int TotalAttValues;
  
 //�������
  private int NumClasses;
  
 //�������� ��������ܹ���������   ��
  private int NumAttributes;
  
 //ʵ������   ��
  private int NumInstances;
  
  private int ClassIndex;
  
  private double [] ClassCounts_weight;
  
  private double total_weight;
  
  private double [][] Distributions;
 
  public void buildClassifier(Instances instances) throws Exception {
	 
    NumClasses = instances.numClasses();  
    NumAttributes = instances.numAttributes();   
    NumInstances = instances.numInstances();      
    ClassIndex = instances.classIndex();      
    TotalAttValues = 0;
    
     m_Instances = new Instances(instances);
    AttributeIndex = new int[NumAttributes];
    AttValuesCounts = new int[NumAttributes];
    
    for(int i = 0 ; i < NumAttributes ; i++) {
      if(i == ClassIndex) {  //���ֳ�label����
          AttributeIndex[i] = -1;
          AttValuesCounts[i] = NumClasses;
      }
      else {
    	  AttributeIndex[i] = TotalAttValues;   
          AttValuesCounts[i] = instances.attribute(i).numValues();    
          TotalAttValues += AttValuesCounts[i];   
      }
    }
   
  }
   
   //���ݸ��Ĳ���ʾ��ȥͳ�Ƹ���label�ĸ���ֵ
   public double [] distributionForInstance(Instance instance) throws Exception {
	       
	  //������ʾ�������ݼ�������ʾ���������ƶȱȽϣ���ø���ʾ����Ȩֵ
	    double[] int_weighted = new double[NumInstances];
	    Arrays.fill(int_weighted,1.0);
	    for(int i = 0; i < NumInstances; i++) {
	    	for(int j = 0; j < NumAttributes; j++) {
	    		if(instance.value(j) == (double)m_Instances.instance(i).value(j)) {
	    			int_weighted[i]++;			
	    		}     
	    	} 
	    	m_Instances.instance(i).setWeight(int_weighted[i]);
	    }
	   
	    //��ȡȨ����ֵ�͸���label��Ȩ��ֵ
	    Distributions = new double[NumClasses][TotalAttValues];
	    ClassCounts_weight = new double[NumClasses];
	    total_weight = 0;
	    for(int i = 0; i < NumInstances; i++) {
	    	int classValue=(int)m_Instances.instance(i).classValue();
	    	total_weight += m_Instances.instance(i).weight();    //Ȩ����ֵ
	    	ClassCounts_weight[classValue] +=  m_Instances.instance(i).weight();  //labelȨ��ֵ
	    	int[] att_index = new int[NumAttributes];
	    	for(int j = 0; j < NumAttributes; j++) {
	    		if(j != ClassIndex){
	            	att_index[j] = AttributeIndex[j] + (int)m_Instances.instance(i).value(j);
	            	Distributions[classValue][att_index[j]] +=  m_Instances.instance(i).weight();            
	            }
	    		else
	    			att_index[j] = -1;
	    	}
	    } 
	   
	   //1�����P��C�� �������
	   double [] prior_prob = new double[NumClasses];
	   for(int i = 0; i < NumClasses; i++)
	   {
		   prior_prob[i] = (ClassCounts_weight[i] + 1.0)/(total_weight + NumClasses);
	   }
	   
	   //����ʾ��������ֵindex
	   int[] instance_index = new int[NumAttributes];
	   for(int m = 0; m < NumAttributes; m++) {
	       if(m == ClassIndex)
	    	   instance_index[m] = -1;
	       else
	    	   instance_index[m] = AttributeIndex[m] + (int)instance.value(m);
	     }
	   
	   //2����P��Xi|Ci������������
	   double [] con_prob = new double[NumClasses];
	   Arrays.fill(con_prob,1.0);
	   for(int j = 0; j < NumClasses; j++)
	   {
		   for(int k = 0; k < NumAttributes; k++) {
			   if(instance_index[k] == -1) continue;  //��ȥlabel
			   con_prob[j] *= (Distributions[j][instance_index[k]] + 1.0)/(ClassCounts_weight[j] + AttValuesCounts[k]);
		   }
	    }
	   
	    //3��P��C��* P��Xi|Ci��
	    double [] probs = new double[NumClasses];
	    for(int l = 0 ; l < NumClasses ; l++) {
		  probs[l] = prior_prob[l] * con_prob[l];
	     }
	         
        Utils.normalize(probs); 
        return probs;
   }
    
   //Ԥ��һ��Instance��label
   public double classifyInstance(Instance instance) throws Exception {
	
	   double [] dist = distributionForInstance(instance);
	   if(dist == null) {
		   throw new Exception("Null distribution predicted");
	    }
	   double max = 0;    //���������
	   int maxIndex = 0;    //���������ڵ�label
	   for (int i = 0; i < dist.length; i++) {
			if (dist[i] > max) {
			  maxIndex = i;
			  max = dist[i];
			}
	   }
	   if (max > 0) {
			return maxIndex;
	   } else {
			return Utils.missingValue();
        }
   }

   
   public static double Sigmoid(double x){
	   return 1.0/(1+Math.exp(-x));    
   }
   
public static void main(String [] argv) {
	  
	  runClassifier(new IWNB(), argv);

  }

}