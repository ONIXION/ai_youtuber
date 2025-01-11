using System.Collections.Generic;

public class ReceiveMessageFormat
{
    public string reply;
    public string action;
    public string emotion;
}

public static class GlobalVariables
{
    // ReceiveMessageFormatの配列を保持する変数
    public static List<ReceiveMessageFormat> AgentQueue = new List<ReceiveMessageFormat>();
    public static List<ReceiveMessageFormat> CommentQueue = new List<ReceiveMessageFormat>();
    public static List<ReceiveMessageFormat> MessageQueue = new List<ReceiveMessageFormat>();
    public static int BooyomiState = 0; // 棒読みちゃん 0:停止 1:音声合成中 2:音声出力中
    public static int AivisState = 0; // Aivis 0:停止 1:音声合成中 2:音声出力中
}

public enum Emotion{
    normal, // 0
    happy, // 1
    angry, // 2
    sad, // 3
    surprised, // 4
    shy, // 5
    excited, // 6
    smug, // 7
    calm, // 8
    waiting // 9
}

public enum Morph
{
    komaru = 4,
    hohozome = 5,
    koukakuage = 7,
    bikkuri = 8,
    okori = 9,
    nikori = 10,
    mayu_ue = 11,
    mayu_sita = 12,
    mabataki = 13,
    zitome = 14,
    niramu = 15,
    hitomi_small = 16,
    hitomi_large = 17,
    nagomi = 19,
    ee = 21,
    pero = 22,
    warai = 43,
    niyari = 44,
    wink_left = 45,
    wink_right = 46,
    heart = 49,
    star = 50,
    high_light_off = 52,
}