package lbfgsb;

public class LBFGSBException extends Exception {
    private static final long serialVersionUID = 1L;
    public LBFGSBException(String message) { super(message); }
    public LBFGSBException(String message, Throwable cause) { super(message, cause); }
}
