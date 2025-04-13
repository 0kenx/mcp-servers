function App() {
    return (
        <div className="app">
            <h1>Hello, JSX!</h1>
            <Component prop={value} />
            {items.map(item => <Item key={item.id} {...item} />)}
        </div>
    );
}

const Component = ({ name, data }) => (
    <div>
        <h2>{name}</h2>
        <pre>{JSON.stringify(data, null, 2)}</pre>
    </div>
);

class ClassComponent extends React.Component {
    render() {
        return <div>{this.props.children}</div>;
    }
}