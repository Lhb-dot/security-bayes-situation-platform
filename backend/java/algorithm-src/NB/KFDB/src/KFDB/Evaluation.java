package KFDB;


import java.util.Random;


import weka.classifiers.AbstractClassifier;
import weka.classifiers.Classifier;
import weka.classifiers.evaluation.output.prediction.AbstractOutput;
import weka.core.Instances;
import weka.filters.Filter;
public class Evaluation extends weka.classifiers.evaluation.Evaluation {

	double trainTime = 0;
	double testTime = 0;
	
	public Evaluation(Instances data) throws Exception {
		super(data);
		// TODO Auto-generated constructor stub
	}

	private static final long serialVersionUID = 1L;

	public void crossValidateModel(Classifier classifier, Instances data, int numFolds, int run, String m_s, Random random, int K)
			throws Exception {
		crossValidateModel(classifier, data, numFolds, run,  m_s, random, K, new Object[0]);
	}

	/**
	 * Performs a (stratified if class is nominal) cross-validation for a classifier
	 * on a set of instances. Performs a deep copy of the classifier before each
	 * call to buildClassifier() (just in case the classifier is not initialized
	 * properly).
	 *
	 * @param classifier  the classifier with any options set.
	 * @param data        the data on which the cross-validation is to be performed
	 * @param numFolds    the number of folds for the cross-validation
	 * @param random      random number generator for randomization
	 * @param forPrinting varargs parameter that, if supplied, is expected to hold a
	 *                    weka.classifiers.evaluation.output.prediction.AbstractOutput
	 *                    object or a StringBuffer for model output
	 * @throws Exception if a classifier could not be generated successfully or the
	 *                   class is not defined
	 */
	public void crossValidateModel(Classifier classifier, Instances data, int numFolds, int run, String ms, Random random, int K,
			Object... forPrinting) throws Exception {

		// Make a copy of the data we can reorder
		data = new Instances(data);
		data.randomize(random);
		if (data.classAttribute().isNominal()) {
			data.stratify(numFolds);
		}

		AbstractOutput classificationOutput = null;
		if (forPrinting.length > 0 && forPrinting[0] instanceof AbstractOutput) {
			// print the header first
			classificationOutput = (AbstractOutput) forPrinting[0];
			classificationOutput.setHeader(data);
			classificationOutput.printHeader();
		}
		double[] errorRate = new double[numFolds];
		double errorNum = 0;
		double[]  Precision = new double[numFolds];
		double  PrecisionNum = 0;
					
		// Do the folds
		for (int i = 0; i < numFolds; i++) {
			
			// divide the training set and test set
			Instances train = data.trainCV(numFolds, i, random);
			setPriors(train);
			Classifier copiedClassifier = AbstractClassifier.makeCopy(classifier);
			Instances test = data.testCV(numFolds, i);
			
			//training
			double start1 = System.currentTimeMillis();
			copiedClassifier.buildClassifier(train);
			trainTime = System.currentTimeMillis() - start1;
			if (classificationOutput == null && forPrinting.length > 0) {
				((StringBuffer) forPrinting[0])
						.append("\n=== Classifier model (training fold " + (i + 1) + ") ===\n\n" + copiedClassifier);
			}
			
			//test
			double start2 = System.currentTimeMillis();
			if (classificationOutput != null) {
				evaluateModel(copiedClassifier, test, forPrinting);
				
			} else {
				evaluateModel(copiedClassifier, test);	
			}
			testTime = System.currentTimeMillis() - start2;
			m_NumFolds = numFolds;
			
			// record the error rate and accuracy of each fold
			if(i!=0) 
			{
				errorRate[i] = (incorrect() - errorNum)/test.numInstances();
				errorNum = incorrect();
				Precision[i] = (correct() - PrecisionNum)/test.numInstances();
				PrecisionNum = correct();
			}
			else{
				errorRate[i] = errorRate();
				errorNum = incorrect();
				Precision[i] = 1 - errorRate();
				PrecisionNum = correct();
			}
			
	       String datasetName = test.relationName().split("-weka")[0];
	       //output error rate and precision for fold
	       System.out.println(datasetName+","+ String.valueOf(run+1) + "," + String.valueOf(i+1) + "," + "KFDB(K="+ K +")," + errorRate[i]*100.0 + "," + Precision[i]*100.0 );
			
		} //do the folds
	
		if (classificationOutput != null) {
			classificationOutput.printFooter();
		}
	}
	
}
