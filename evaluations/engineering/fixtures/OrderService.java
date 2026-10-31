// Deliberately unsafe Spring fixture. NEVER deploy.
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
class OrderService {
    public void place(String password) {
        System.out.println("password=" + password); // sensitive credential logged
        this.persist(); // self-invocation bypasses proxy transaction advice
    }

    @Transactional
    public void persist() {
        // imagine repository writes here
    }
}
