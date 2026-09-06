
package weka.classifiers.mkx.DIWNB;

import weka.core.*;
import weka.classifiers.*;

/**
 * Implement the DWNB classifier.
 */
public class DWNB extends AbstractClassifier implements OptionHandler{

  /** The base classifier to use */
  private Classifier m_Classifier = new weka.classifiers.bayes.NaiveBayes();

  /** The number of the maximum iteration */
  private int m_numIteration=15;

  /**
   * Generates the classifier.
   *
   * @param instances set of instances serving as training data
   * @exception Exception if the classifier has not been generated successfully
   */
  public void buildClassifier(Instances instances) throws Exception {

    Instances data=new Instances(instances);
    m_Classifier.buildClassifier(data);
    double weight;
    double [] prob;
    for (int j=0;j<m_numIteration;j++){
        for(int i=0;i<data.numInstances();i++){
            prob = m_Classifier.distributionForInstance(data.instance(i));
            weight=data.instance(i).weight()+(1-prob[(int)data.instance(i).classValue()]);
            data.instance(i).setWeight(weight);
        }
        m_Classifier.buildClassifier(data);
    }
  }

  /**
   * Set the base learner.
   *
   * @param newClassifier the classifier to use.
   */
  public void setClassifier(Classifier newClassifier) {

    m_Classifier = newClassifier;
  }

  /**
   * Get the classifier used as the base learner.
   *
   * @return the classifier used as the classifier
   */
  public Classifier getClassifier() {

    return m_Classifier;
  }

  /**
   * Get the random number seed
   *
   * @return the seed
   */
  public int getNumIteration () {
    return  m_numIteration;
  }

  /**
   * Set the random number seed
   *
   * @param s the seed
   */
  public void setNumIteration (int q) {
    m_numIteration = q;
  }

  /**
   * Gets the current settings of RODANB
   *
   * @return an array of strings suitable for passing to setOptions()
   */
  public void setOptions (String[] options) throws Exception {
    String classifierName = Utils.getOption('C', options);
    if (classifierName.length() != 0) {
      setClassifier( AbstractClassifier.forName(classifierName,Utils.partitionOptions(options)));
    }
    String optionString = Utils.getOption('Q', options);
    if (optionString.length() != 0) {
      setNumIteration(Integer.parseInt(optionString));
    }
  }

  /**
   * Gets the current settings of RODANB
   *
   * @return an array of strings suitable for passing to setOptions()
   */
  public String[] getOptions () {
    String[] options = new String[4];
    int current = 0;
    options[current++] = "-C";
    options[current++] = getClassifier().getClass().getName();
    options[current++] = "-Q";
    options[current++] = "" + getNumIteration ();
    while (current < options.length) {
      options[current++] = "";
    }
    return  options;
  }

   /**
    * Calculates the class membership probabilities for the given test instance
    *
    * @param instance the instance to be classified
    * @return predicted class probability distribution
    * @exception Exception if there is a problem generating the prediction
    */
   public double [] distributionForInstance(Instance instance) throws Exception {

     return m_Classifier.distributionForInstance(instance);
   }

  /**
   * Main method for testing this class.
   *
   * @param argv the options
   */
  public static void main(String [] argv) {
    try {
       System.out.println(Evaluation.evaluateModel(new DWNB(), argv));
    }
    catch (Exception e) {
       e.printStackTrace();
       System.err.println(e.getMessage());
    }
  }

}
