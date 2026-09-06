package lbfgsb;

public class Bound {
    public Double lowerBound;
    public Double upperBound;
    public Bound(Double lowerBound, Double upperBound) {
        this.lowerBound = lowerBound;
        this.upperBound = upperBound;
    }
    public boolean isLowerBoundDefined() { return lowerBound != null; }
    public boolean isUpperBoundDefined() { return upperBound != null; }
    @Override public String toString() { return "[" + lowerBound + ", " + upperBound + "]"; }
}
