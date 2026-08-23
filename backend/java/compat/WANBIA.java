package weka.classifiers.bayes.WANBIA;

/**
 * Compatibility class for the supplied A2WNB source.
 * The source references WANBIA, while the delivered source bundle does not
 * include that historical class. Weka's NaiveBayes is the compatible second
 * stage classifier expected by A2WNB's Classifier API.
 */
public class WANBIA extends weka.classifiers.bayes.NaiveBayes {
    private static final long serialVersionUID = 1L;
}
