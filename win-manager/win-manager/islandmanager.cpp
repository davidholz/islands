#include <array>
#include <memory>
#include <stdio.h>
#include <string>
#include <vector>
#include <iostream>



#include "islandmanager.h"

IslandManager::IslandManager(){}
IslandManager::~IslandManager(){}

IslandManager& IslandManager::getInstance(){
    static IslandManager im;
    return im;
}

int IslandManager::launchIsland(){
    std::string a = this->exec("vboxmanage startvm Island");
    return 0;
}

std::string IslandManager::exec(std::string command){
    std::array<char, 128> buffer;
    //std::vector<char*> resChunks;
    //char* result;
    std::shared_ptr<FILE> pipe(_popen(command.c_str(), "r"), pclose);
    if (!pipe) throw std::runtime_error("popen() failed!");
    while (!feof(pipe.get())) {
        if (fgets(buffer.data(), 128, pipe.get()) != nullptr){
               //resChunks.push_back(buffer.data());
            std::cout<<buffer.data();
        }
    }

    return "blank";
    //return result;
}


