#include <iostream>

namespace cli_tools {
    void printMessage() {
        std::cout << "Hello from the cli_tools namespace!" << std::endl;
    }
}

int main() {
    cli_tools::printMessage();
    return 0;
}