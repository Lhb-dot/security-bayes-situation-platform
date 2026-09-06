package weka.classifiers.mkx.DIWNB;

import java.util.Arrays;

import weka.classifiers.AbstractClassifier;
import weka.classifiers.Classifier;
import weka.classifiers.lazy.IBk;
import weka.core.Instance;
import weka.core.Instances;

public class KNNs_hard extends AbstractClassifier {
	
	
	private static final long serialVersionUID = 1L;
	
	private Instances instances;
	
	private int[] KValues;   
	
	private int NumClasses;
	
	private IBk knn;
	
	public static final int BEST_NUM = 5;
	
	public static final int TRAIN_NUM = 15;

	
	/**
	 * Select multiple KNN classifiers with the lowest error rate. 
	 *
	 * @param instances 
	 *            set of instances serving as training data
	 */
	@Override
	public void buildClassifier(Instances data) throws Exception {

		int[] incorrectNums = new int[TRAIN_NUM];
	    instances = new Instances(data);
	    NumClasses = instances.numClasses();
	  
	    knn = new IBk();
		knn.buildClassifier(instances);
		
		IBk searchKnn = new IBk();
		searchKnn.buildClassifier(instances);
	
		for(int i = 0; i < instances.numInstances(); i++)  {
			//find multiple neighbors at once
			Instances neighbors = searchKnn.getNearestNeighbourSearchAlgorithm().kNearestNeighbours(instances.instance(i), TRAIN_NUM + 1);
			//remove itself
			neighbors.delete(0);  
			//evaluate the performance of different KNNs 
			for(int j = 0; j < TRAIN_NUM; j++)  {
				int[] neighborClass = new int [instances.numClasses()]; 
				Arrays.fill(neighborClass,0);
				
				//obtain current instance's prediction class label
				for(int m = 0; m <= j; m++)  {
					neighborClass[(int)neighbors.instance(m).classValue()]++; 
			    }
				int max = neighborClass[0];
				int index = 0;
				for(int n = 1; n < instances.numClasses(); n++) {
					if(max < neighborClass[n]) {
						max = neighborClass[n];
						index = n;
					}
				}
				
				//judge whether the prediction class label is the same as the real class label
			    if(index != (int)instances.instance(i).classValue())	{
			    	incorrectNums[j]++;
			    }
		    }			
	    }
		
		ArrayCom[] KValues_elements = new ArrayCom[TRAIN_NUM]; 
		for(int j = 0; j < TRAIN_NUM; j++)  {
			KValues_elements[j] = new ArrayCom(incorrectNums[j]/(double)instances.numInstances(), j + 1);  
		}
        Arrays.sort(KValues_elements); 
        KValues = new int [BEST_NUM];
     	for (int i = 0; i < BEST_NUM; i++) {  
     		KValues[i] = KValues_elements[i].index;  
     	} 	
   }
	
	
	/**
	 * Uses KNN classifiers selected to calculate the class label of the given instance, 
	 * and use their as the attribute value in the generated view.  
	 *
	 * @param instance 
	 * 			the instance to be built to generate view
	 * @return attribute value of the given instance in the generated view 
	 */
	  public String [] distributionForInstance2(Instance instance) throws Exception {
		  String[] class_predictions = new String [BEST_NUM]; 
		  //get neighbors
		  Instances neighbors = knn.getNearestNeighbourSearchAlgorithm().kNearestNeighbours(instance, TRAIN_NUM);
		  for(int i = 0; i < BEST_NUM; i++)  {
			  double[] class_nums = new double [NumClasses];
			  //obtain current instance's prediction class label using KNNs selected
			  for(int j = 0; j < KValues[i]; j++) {
				  class_nums[(int) neighbors.instance(j).classValue()]++;
			  }
		      double max = class_nums[0];
			  int index = 0;
			  for(int n = 1; n < NumClasses; n++) {
				  if(max < class_nums[n]) {
					  max = class_nums[n];
					  index = n;
				  }
			  } 
			  class_predictions[i] = instances.classAttribute().value(index);
		  }
		  return class_predictions; 
	  }
	  
	  public static void main(String[] args) {
		runClassifier(new  KNNs_hard(), args);
	  }
	
}

