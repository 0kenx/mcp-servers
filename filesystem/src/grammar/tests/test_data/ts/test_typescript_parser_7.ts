@Component({
    selector: 'app-root',
    template: '<div>Hello</div>'
})
class AppComponent {
    constructor() {}
}

@Injectable()
class Service {
    @Input() data: string;
    
    @Log()
    doSomething() {}
}