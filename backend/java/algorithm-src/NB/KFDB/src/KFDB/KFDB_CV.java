package KFDB;

import java.io.BufferedReader;
import java.io.File;
import java.io.FileReader;
import java.util.Arrays;
import java.util.Random;
import weka.core.Instances;
import weka.core.converters.ArffLoader.ArffReader;

public class KFDB_CV {
     
	private static String data = "E:\\datasets60";    // dataset path
	private static String m_S = "KFDB_MSE";      // model name KFDB_MSE/KFDB_ACC
	private static int m_K = 1;  // maximum number of parents for each attribute
	public static final int BUFFER_SIZE = 10 * 1024 * 1024; 
	private static int foldnum = 5;   //fold number
	private static int m_nExp = 2;    //experiment number
		
	public static void main(String[] args) throws Exception {
		
		if (data.isEmpty()) {
			System.err.println("No Training File given");
			System.exit(-1);
		}
		
		 File Filess = new File(data); 
		 if (!Filess.exists()) {
			System.err.println("File not found!");
			System.exit(-1);
		}
		 File[] files = Filess.listFiles();
		 Arrays.sort(files);
		 
		 String[] datasetName = new String[files.length];
		 		
		    //Multiple datasets
			for(int DatasetNum = 0; DatasetNum < files.length; DatasetNum++ ) {
				
				long seed = 25011990; 
				BufferedReader reader = new BufferedReader(new FileReader(files[DatasetNum]));
				ArffReader arff = new ArffReader(reader);
				Instances data = arff.getData();
				data.setClassIndex(data.numAttributes() - 1);
				
				//Multiple run
				for (int run = 0; run < m_nExp; run++) {
				
					Random random = new Random(seed);
					wdBayesOnlinePYP learner = new wdBayesOnlinePYP();
					learner.set_m_S(m_S);
					learner.setK(m_K);
					Evaluation eva = new Evaluation(data);
					eva.crossValidateModel(learner, data, foldnum, run, m_S, random, m_K);
					datasetName[DatasetNum] = data.relationName().split("-weka")[0];					
					seed++;
				    } // Ends No. of Experiments
				
			}// Ends No. of datasets
		
      }
	 
}
