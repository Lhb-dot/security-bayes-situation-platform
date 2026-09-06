package weka.classifiers.mkx.DIWNB;
import weka.core.*;
import java.util.Arrays;
import weka.classifiers.*;
 
/**
 * Implement the FTAWNB_E classifier.
 */
public class AVFWNB extends  AbstractClassifier {
 
  private static final long serialVersionUID = 1L;

 //���Ϊ�У���������ֵΪ�еĶ�ά����  [NumClasses][TotalAttValues]
  private double [][] Distributions;
 
 //�������ǩ��Ȩ��
  private double [] ClassCounts_weight;
  
 //ÿ�����Ժ��ж�������ֵ
  private double [] AttValuesCounts;
 
  //���Բ������±�
  private int []  AttributeIndex;
  
  //����Ȩ��ֵ
  private double [] int_weighted;
  
  
  //��������ֵ��Ƶ��
  private double []attvalue_fre;
  
  //�洢ѵ������
  private Instances m_Instances;
  
 //���е�����ֵ  ����labelֵ  
  private int TotalAttValues;
  
 //�������
  private int NumClasses;
  
 //�������� ��������ܹ���������   ��
  private int NumAttributes;
  
 //ʾ������   ��
  private int NumInstances;
  
  //label�±�
  private int ClassIndex;
  
  //����ʾ��Ȩ��ֵ�Ӻ�
  private double total_weight;
  
 
 
  public void buildClassifier(Instances instances) throws Exception {

	m_Instances = new Instances(instances);
    NumClasses = instances.numClasses();   
    NumAttributes = instances.numAttributes();
    NumInstances = instances.numInstances(); 
    ClassIndex = instances.classIndex();    
    
    TotalAttValues = 0;
    AttributeIndex = new int[NumAttributes];
    AttValuesCounts = new double[NumAttributes];
    for(int i = 0 ; i < NumAttributes ; i++) {
      if(i == ClassIndex) //���ֳ�label����
      {
    	AttributeIndex[i] = -1;
        AttValuesCounts[i] = NumClasses;
       }
      else {
    	 AttributeIndex[i] = TotalAttValues;   
         AttValuesCounts[i] = instances.attribute(i).numValues();   
         TotalAttValues += AttValuesCounts[i]; 
         }
    }
      
     //�����������ֵ��Ƶ��
    attvalue_fre = new double[TotalAttValues];
    for(int j = 0; j < NumInstances; j++) {  
      int[] att_index = new int[NumAttributes];
      for(int i = 0; i < NumAttributes; i++) {
        if(i != ClassIndex){
        	att_index[i] = AttributeIndex[i] + (int)instances.instance(j).value(i);
        	attvalue_fre[att_index[i]] += 1.0/(double)NumInstances;
        }
      }  
    }
   
    //����ʾ��Ȩֵ
    int_weighted = new double[NumInstances];
    for(int j = 0; j < NumInstances; j++) {
    	 int[] att_index = new int[NumAttributes];
    	 for(int i = 0; i < NumAttributes; i++) {
    		 if(i != ClassIndex){ 
    		att_index[i] = AttributeIndex[i] + (int)instances.instance(j).value(i);
            int_weighted[j] += attvalue_fre[att_index[i]] * (double)instances.instance(j).attribute(i).numValues();
    		 }
          }
    	 instances.instance(j).setWeight(int_weighted[j]);
    }
    
    
    //��ȡȨ����ֵ�͸���label��Ȩ��ֵ
    Distributions = new double[NumClasses][TotalAttValues];
    ClassCounts_weight = new double[NumClasses];
    total_weight = 0;
    for(int i = 0; i < NumInstances; i++) {
    	int classValue=(int)instances.instance(i).classValue();
    	total_weight += instances.instance(i).weight();    //Ȩ����ֵ
    	ClassCounts_weight[classValue] +=  instances.instance(i).weight();  //labelȨ��ֵ
    	int[] att_index = new int[NumAttributes];
    	for(int j = 0; j < NumAttributes; j++) {
    		if(j != ClassIndex){
            	att_index[j] = AttributeIndex[j] + (int)instances.instance(i).value(j);
            	Distributions[classValue][att_index[j]] +=  instances.instance(i).weight();            
            }
    		else
    			att_index[j] = -1;
    	}
    } 
    
 }
  

   public double [] distributionForInstance(Instance instance) throws Exception {
 
	   //1�����P��C�� �������
	   double [] prior_prob = new double[NumClasses];
	   for(int i = 0; i < NumClasses; i++)
	   {
		  prior_prob[i] = (ClassCounts_weight[i] + 1.0)/(total_weight + NumClasses);
	   }
	   
	   //����instance������ֵindex
	   int[] instance_index = new int[NumAttributes];
	   for(int m = 0; m < NumAttributes; m++) {
	       if(m != ClassIndex)
	    	   instance_index[m] = AttributeIndex[m] + (int)instance.value(m);
	       else
	    	   instance_index[m] = -1;
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

   
   
public static void main(String [] argv) {
	  
	  runClassifier(new AVFWNB(), argv);

  }

}