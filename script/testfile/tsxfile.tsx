import React, { Component, useState, useEffect, useCallback } from 'react';
import '@/tsxfile.css';
import Button from '@/components/Button';

// 定义接口类型
interface Props {
  initialCount: number;
  message: string;
}

// 定义一个 CSS 模块样式
const styles = {
  container: {
    backgroundColor: '#f0f0f0',
    padding: '20px',
    borderRadius: '8px',
    boxShadow: '0 0 5px rgba(0, 0, 0, 0.2)',
    margin: '20px auto',
    maxWidth: '400px'
  },
  title: {
    color: '#333',
    fontSize: '24px',
    textAlign: 'center'
  },
  button: {
    backgroundColor: '#007bff',
    color: 'white',
    padding: '10px 20px',
    border: 'none',
    borderRadius: '4px',
    cursor: 'pointer',
    margin: '10px'
  },
  input: {
    padding: '10px',
    border: '1px solid #ccc',
    borderRadius: '4px',
    margin: '10px'
  }
};

// 定义一个闭包函数
const createLogger = (prefix: string) => {
  return (message: string) => {
    console.log(`${prefix}: ${message}`);
  };
};

// 自定义 Hook
const useLocalStorage = <T>(key: string, initialValue: T) => {
  const [storedValue, setStoredValue] = useState<T>(() => {
    try {
      const item = window.localStorage.getItem(key);
      return item ? JSON.parse(item) : initialValue;
    } catch (error) {
      console.log(error);
      return initialValue;
    }
  });

  const setValue = (value: T | ((val: T) => T)) => {
    try {
      const valueToStore = value instanceof Function ? value(storedValue) : value;
      setStoredValue(valueToStore);
      window.localStorage.setItem(key, JSON.stringify(valueToStore));
    } catch (error) {
      console.log(error);
    }
  };

  return [storedValue, setValue] as const;
};

// 定义一个类组件
class ClassComponent extends Component<Props> {
  private logger = createLogger('ClassComponent');
  private intervalId: NodeJS.Timeout | null = null;

  constructor(props: Props) {
    super(props);
    this.state = {
      count: props.initialCount
    };
  }

  componentDidMount() {
    this.logger('Component mounted');
    this.intervalId = setInterval(() => {
      this.setState((prevState) => ({
        count: prevState.count + 1
      }));
    }, 1000);
  }

  componentWillUnmount() {
    this.logger('Component will unmount');
    if (this.intervalId) {
      clearInterval(this.intervalId);
    }
  }

  render() {
    const { message } = this.props;
    const { count } = this.state;
    return (
      <div style={styles.container}>
        <h2 style={styles.title}>{message}</h2>
        <p>Class Component Count: {count}</p>
        <Button onClick={() => this.setState({ count: count + 1 })}></Button>
      </div>
    );
  }
}

// 定义一个函数组件
const FunctionalComponent = () => {
  const [count, setCount] = useState(0);
  const [inputValue, setInputValue] = useState('');
  const [storedValue, setStoredValue] = useLocalStorage('myData', 'default');

  const increment = useCallback(() => {
    setCount((prevCount) => prevCount + 1);
  }, []);

  const decrement = useCallback(() => {
    setCount((prevCount) => prevCount - 1);
  }, []);

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setInputValue(e.target.value);
  };

  const saveToLocalStorage = () => {
    setStoredValue(inputValue);
  };

  useEffect(() => {
    console.log('Count changed:', count);
    return () => {
      console.log('Cleanup effect');
    };
  }, [count]);

  return (
    <div style={styles.container}>
      <h2 style={styles.title}>Functional Component</h2>
      <p>Count: {count}</p>
      <button style={styles.button} onClick={increment}>
        Increment
      </button>
      <button style={styles.button} onClick={decrement}>
        Decrement
      </button>
      <input
        style={styles.input}
        type="text"
        value={inputValue}
        onChange={handleInputChange}
        placeholder="Enter something"
      />
      <button style={styles.button} onClick={saveToLocalStorage}>
        Save to Local Storage
      </button>
      <p>Stored Value: {storedValue}</p>
    </div>
  );
};

// 主组件
const App: React.FC = () => {
  return (
    <div>
      <ClassComponent initialCount={0} message="Class Component Example" />
      <FunctionalComponent />
    </div>
  );
};

export default App;