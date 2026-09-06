package weka.classifiers.mkx.DIWNB;

public class ArrayCom implements Comparable<ArrayCom> {  
    double value;  
    int index;  
  
    public ArrayCom(double value, int index) {  
        this.value = value;  
        this.index = index;  
    }
    
    @Override  
    public int compareTo(ArrayCom o) {  
    	if(this.value > o.value) {
    	   return 1;
    	}else if(this.value < o.value) {
    	   return -1;
        }
    	return 0;
    }
}