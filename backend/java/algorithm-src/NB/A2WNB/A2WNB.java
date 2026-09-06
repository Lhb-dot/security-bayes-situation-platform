package weka.classifiers.zh.A2WNB;

import java.util.ArrayList;
import java.util.List;

import weka.classifiers.AbstractClassifier;
import weka.classifiers.Classifier;
import weka.core.Attribute;
import weka.core.FastVector;
import weka.core.Instance;
import weka.core.Instances;
import weka.core.OptionHandler;
import weka.core.Utils;
import weka.core.WeightedInstancesHandler;

public class A2WNB extends AbstractClassifier implements OptionHandler, WeightedInstancesHandler {
	
	private static final long serialVersionUID = 1L;

	/** The base classifier to use */
	public Classifier m_Classifier = new RODE();
	
	public Classifier m_Classifier2 = new weka.classifiers.bayes.WANBIA.WANBIA();
	
	public RODE rode;
	
	Instances insts;

	private int numAtt;

	public void buildClassifier(Instances data) throws Exception {

		m_Classifier.buildClassifier(data);
		rode = (RODE)m_Classifier;
	
		insts = new Instances(data);
		numAtt = data.numAttributes()-1;
		
		for (int i = numAtt; i < numAtt+numAtt; i++) {
			FastVector list = new FastVector();
			for (int j = 0; j < data.numClasses(); j++) {
				list.addElement(String.valueOf(j));
			}
			Attribute att = new Attribute("att" + (i+1), list);
			insts.insertAttributeAt(att, i);
		}
		
		for(int i=0; i<data.numInstances(); i++) {
			String str = rode.distributionForInstance2(data.instance(i));
			String[] tmp = str.split(",");
			int index = 0;
			for(int j=numAtt; j<numAtt+numAtt; j++) {
				insts.instance(i).setValue(j, tmp[index]);
				index++;
			}
		}
		
		m_Classifier2.buildClassifier(insts);
		
	}
	

	public double[] distributionForInstance(Instance instance) throws Exception {
		
		Instances insts2 = new Instances(insts);
		
		rode = (RODE)m_Classifier;
		
		int index = 0;
		for(int j=0; j<numAtt; j++) {
			insts2.instance(0).setValue(j, instance.value(j));
			index++;
		}
		String str = rode.distributionForInstance2(instance);
		String[] tmp = str.split(",");
		index = 0;
		for(int j=numAtt; j<numAtt+numAtt; j++) {
			insts2.instance(0).setValue(j, tmp[index]);
			index++;
		}
		
		return m_Classifier2.distributionForInstance(insts2.instance(0));
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
	
	public Classifier getM_Classifier2() {
		return m_Classifier2;
	}


	public void setM_Classifier2(Classifier m_Classifier2) {
		this.m_Classifier2 = m_Classifier2;
	}

	/**
	 * Gets the current settings of RODANB
	 *
	 * @return an array of strings suitable for passing to setOptions()
	 */
	public void setOptions(String[] options) throws Exception {
		String classifierName = Utils.getOption('C', options);
		if (classifierName.length() != 0) {
			setClassifier(AbstractClassifier.forName(classifierName, Utils.partitionOptions(options)));
		}
		String classifier2Name = Utils.getOption('Q', options);
		if (classifier2Name.length() != 0) {
			setM_Classifier2(AbstractClassifier.forName(classifier2Name, Utils.partitionOptions(options)));
		}
	}

	/**
	 * Gets the current settings of RODANB
	 *
	 * @return an array of strings suitable for passing to setOptions()
	 */
	public String[] getOptions() {
		String[] options = new String[4];
		int current = 0;
		options[current++] = "-C";
		options[current++] = getClassifier().getClass().getName();
		options[current++] = "-Q";
		options[current++] = getM_Classifier2().getClass().getName();
		while (current < options.length) {
			options[current++] = "";
		}
		return options;
	}

	public static void main(String[] args) {

		runClassifier(new A2WNB(), args);
	}

}
